"""Public/resident Benefits routes (programs and applications)."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

try:
    from apps.api import db
    from apps.api.models.benefit import BenefitProgram, BenefitApplication
    from apps.api.models.user import User
    from apps.api.models.municipality import Municipality
    from apps.api.utils import (
        validate_required_fields,
        ValidationError,
        fully_verified_required,
        save_benefit_document,
    )
except ImportError:
    from __init__ import db
    from models.benefit import BenefitProgram, BenefitApplication
    from models.user import User
    from models.municipality import Municipality
    from utils import (
        validate_required_fields,
        ValidationError,
        fully_verified_required,
        save_benefit_document,
    )


benefits_bp = Blueprint('benefits', __name__, url_prefix='/api/benefits')


@benefits_bp.route('/programs', methods=['GET'])
def list_programs():
    """Public list of active benefit programs."""
    try:
        municipality_id = request.args.get('municipality_id', type=int)
        program_type = request.args.get('type')

        query = BenefitProgram.query.filter_by(is_active=True)
        if municipality_id:
            query = query.filter((BenefitProgram.municipality_id == municipality_id) | (BenefitProgram.municipality_id.is_(None)))
        if program_type:
            query = query.filter(BenefitProgram.program_type == program_type)

        programs = query.order_by(BenefitProgram.created_at.desc()).all()

        # Auto-complete expired programs before returning
        now = datetime.utcnow()
        changed = False
        for p in programs:
            try:
                if p.is_active and p.duration_days and p.created_at:
                    if p.created_at + timedelta(days=int(p.duration_days)) <= now:
                        p.is_active = False
                        p.is_accepting_applications = False
                        p.completed_at = now
                        changed = True
            except Exception:
                pass
        if changed:
            db.session.commit()
            # Filter out programs that were just set inactive
            programs = [p for p in programs if p.is_active]
        # Compute beneficiaries as count of approved applications per program (public view)
        try:
            ids = [p.id for p in programs] or []
            if ids:
                rows = (
                    db.session.query(
                        BenefitApplication.program_id,
                        db.func.count(BenefitApplication.id)
                    )
                    .filter(
                        BenefitApplication.program_id.in_(ids),
                        BenefitApplication.status == 'approved'
                    )
                    .group_by(BenefitApplication.program_id)
                    .all()
                )
                counts = {pid: int(cnt) for pid, cnt in rows}
                for p in programs:
                    try:
                        p.current_beneficiaries = counts.get(p.id, 0)
                    except Exception:
                        pass
        except Exception:
            pass

        return jsonify({'programs': [p.to_dict() for p in programs], 'count': len(programs)}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to get programs', 'details': str(e)}), 500


@benefits_bp.route('/programs/<int:program_id>', methods=['GET'])
def get_program(program_id: int):
    try:
        program = BenefitProgram.query.get(program_id)
        if not program or not program.is_active:
            return jsonify({'error': 'Program not found'}), 404
        return jsonify(program.to_dict()), 200
    except Exception as e:
        return jsonify({'error': 'Failed to get program', 'details': str(e)}), 500


@benefits_bp.route('/applications', methods=['POST'])
@jwt_required()
@fully_verified_required
def create_application():
    """Create a benefit application for the current user."""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        data = request.get_json() or {}
        required = ['program_id']
        validate_required_fields(data, required)

        program = BenefitProgram.query.get(int(data['program_id']))
        if not program or not program.is_active:
            return jsonify({'error': 'Invalid program'}), 400

        # Municipality scoping: allow province-wide (None) or user's municipality
        if program.municipality_id and user.municipality_id != program.municipality_id:
            return jsonify({'error': 'Program not available for your municipality'}), 403

        # Generate application number
        count = BenefitApplication.query.count() + 1
        app_number = f"APP-{user.municipality_id}-{user_id}-{count}"

        app = BenefitApplication(
            application_number=app_number,
            user_id=user_id,
            program_id=program.id,
            application_data=data.get('application_data') or {},
            supporting_documents=[],
            status='pending',
        )
        db.session.add(app)
        db.session.commit()

        return jsonify({'message': 'Application created successfully', 'application': app.to_dict()}), 201
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create application', 'details': str(e)}), 500


@benefits_bp.route('/my-applications', methods=['GET'])
@jwt_required()
def my_applications():
    try:
        user_id = get_jwt_identity()
        apps = BenefitApplication.query.filter_by(user_id=user_id).order_by(BenefitApplication.created_at.desc()).all()
        return jsonify({'applications': [a.to_dict() for a in apps], 'count': len(apps)}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to get applications', 'details': str(e)}), 500


@benefits_bp.route('/applications/<int:application_id>/upload', methods=['POST'])
@jwt_required()
@fully_verified_required
def upload_application_doc(application_id: int):
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        app = BenefitApplication.query.get(application_id)
        if not app:
            return jsonify({'error': 'Application not found'}), 404
        if app.user_id != user_id:
            return jsonify({'error': 'Forbidden'}), 403

        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['file']

        municipality = Municipality.query.get(user.municipality_id)
        municipality_slug = municipality.slug if municipality else 'unknown'

        rel_path = save_benefit_document(file, app.id, municipality_slug)

        existing = app.supporting_documents or []
        existing.append(rel_path)
        app.supporting_documents = existing
        db.session.commit()

        return jsonify({'message': 'File uploaded', 'path': rel_path, 'application': app.to_dict()}), 200
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to upload file', 'details': str(e)}), 500


