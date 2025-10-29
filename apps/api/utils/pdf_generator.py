"""
Dynamic PDF generator for document requests (template-free).

Uses reportlab to render an official-looking document with:
- Government header and municipality name
- Title from document type config
- Body text with simple {{placeholders}} replacement
- Border, watermark (seal/logo if available), and optional QR code

Entry point: generate_document_pdf(request, document_type, user) -> (abs_path, rel_path)

The file is saved under the Flask UPLOAD_FOLDER at:
  generated_docs/{municipality_slug}/{request_id}.pdf

Returns absolute path and relative path (from UPLOAD_FOLDER) for storage in DB and public URL building.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Tuple, Optional
from datetime import datetime

from flask import current_app

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.units import mm


def _slugify(name: str) -> str:
    return (
        (name or "")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
    )


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _load_document_types() -> Dict[str, Dict]:
    # Load JSON config with type definitions
    try:
        # apps/api is current_app.root_path
        cfg_path = Path(current_app.root_path) / "config" / "documentTypes.json"
        if not cfg_path.exists():
            return {}
        import json

        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_municipality_officials() -> Dict[str, Dict]:
    # Load JSON config with mayor/vice mayor info
    try:
        cfg_path = Path(current_app.root_path) / "config" / "municipalityOfficials.json"
        if not cfg_path.exists():
            return {}
        import json

        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_barangay_officials() -> Dict[str, Dict[str, str]]:
    """Load Punong Barangay names per municipality and barangay.

    File format: { "Municipality": { "Barangay Name": "Punong Barangay Name" } }
    """
    try:
        cfg_path = Path(current_app.root_path) / "config" / "barangayOfficials.json"
        if not cfg_path.exists():
            return {}
        import json

        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _resolve_logo_paths(municipality_name: str) -> Tuple[Path | None, Path | None]:
    """Return (municipal_logo, province_logo) if available."""
    # Compute repository root from Flask app root (apps/api)
    repo_root = Path(current_app.root_path).parents[1]
    mun_dir = repo_root / "public" / "logos" / "municipalities"
    prov_dir = repo_root / "public" / "logos" / "zambales"

    slug = _slugify(municipality_name)
    # Try flat structure first (files directly in municipalities/)
    candidates = [
        mun_dir / f"{municipality_name}.png",
        mun_dir / f"{municipality_name}.jpg",
        mun_dir / f"{slug}.png",
        mun_dir / f"{slug}.jpg",
    ]
    mun_logo = next((p for p in candidates if p.exists()), None)
    
    # Try nested structure (municipalities/MunicipalityName/*.png)
    if not mun_logo and mun_dir.exists():
        for folder_variant in [municipality_name, slug, municipality_name.replace(' ', '')]:
            nested = mun_dir / folder_variant
            if nested.exists() and nested.is_dir():
                # Look for seal files first, then any png/jpg
                seal_patterns = ['*seal*.png', '*Seal*.png', '*logo*.png', '*Logo*.png']
                for pattern in seal_patterns:
                    matches = sorted(nested.glob(pattern))
                    if matches:
                        mun_logo = matches[0]
                        break
                if mun_logo:
                    break
                # Fallback: any png/jpg in folder
                for ext in ['*.png', '*.jpg']:
                    matches = sorted(nested.glob(ext))
                    if matches:
                        mun_logo = matches[0]
                        break
                if mun_logo:
                    break
    
    # Final fallback: first png in flat dir matching slug fragment
    if not mun_logo and mun_dir.exists():
        try:
            for p in sorted(mun_dir.glob("*.png")):
                if slug in p.name.lower().replace('-', '_'):
                    mun_logo = p
                    break
        except Exception:
            pass

    # Province logo fallback
    prov_candidates = list(prov_dir.glob("*.png")) + list(prov_dir.glob("*.jpg"))
    prov_logo = prov_candidates[0] if prov_candidates else None

    return mun_logo, prov_logo


def _simple_template(text: str, ctx: Dict[str, str]) -> str:
    # Very small, safe placeholder replacement for {{key}}
    if not text:
        return ""
    out = text
    for k, v in ctx.items():
        out = out.replace(f"{{{{{k}}}}}", str(v) if v is not None else "")
    return out


def _draw_border(c: canvas.Canvas, margin_mm: float = 12.0):
    width, height = A4
    m = margin_mm * mm
    c.setStrokeColor(colors.HexColor("#003399"))
    c.setLineWidth(2)
    c.rect(m, m, width - 2 * m, height - 2 * m, stroke=1, fill=0)


def _draw_header(c: canvas.Canvas, municipality_name: str, mun_logo: Path | None, prov_logo: Path | None, *, level: str = 'municipal', barangay_name: str = ''):
    width, height = A4
    top_y = height - 30 * mm

    # Left side: Zambales logo (province) and Municipal logo side by side
    logo_size = 18 * mm
    logo_spacing = 22 * mm  # Horizontal spacing between logos
    left_margin = 20 * mm
    
    # Draw province logo (Zambales) first on the left
    if prov_logo and prov_logo.exists():
        try:
            img = ImageReader(str(prov_logo))
            c.drawImage(img, left_margin, top_y - 18 * mm, width=logo_size, height=logo_size, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    
    # Draw municipal logo next to province logo
    if mun_logo and mun_logo.exists():
        try:
            img = ImageReader(str(mun_logo))
            c.drawImage(img, left_margin + logo_spacing, top_y - 18 * mm, width=logo_size, height=logo_size, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    # Right/top: header text
    _set_font(c, "Times-Bold", 12)
    c.drawRightString(width - 20 * mm, top_y, "Republic of the Philippines")
    _set_font(c, "Times-Roman", 11)
    c.drawRightString(width - 20 * mm, top_y - 6 * mm, "Province of Zambales")
    _set_font(c, "Times-Bold", 12)
    c.drawRightString(width - 20 * mm, top_y - 12 * mm, f"Municipality of {municipality_name}")
    if level == 'barangay':
        # Barangay-specific header line
        _set_font(c, "Times-Bold", 11)
        c.drawRightString(width - 20 * mm, top_y - 18 * mm, f"Barangay {barangay_name or 'Hall'}")
        _set_font(c, "Times-Roman", 11)
        c.drawRightString(width - 20 * mm, top_y - 24 * mm, "Office of the Punong Barangay")
    else:
        _set_font(c, "Times-Roman", 11)
        c.drawRightString(width - 20 * mm, top_y - 18 * mm, "Office of the Municipal Mayor")


def _draw_watermark(c: canvas.Canvas, mun_logo: Path | None, opacity: float = 0.25, size_mm: float = 150.0):
    """Draw a semi-transparent watermark centered on the page.

    Uses Pillow to pre-apply opacity so it works even if setFillAlpha is unavailable
    or not honored for images on some ReportLab backends.
    """
    if not mun_logo or not mun_logo.exists():
        return
    width, height = A4
    try:
        logger = getattr(current_app, 'logger', None)
        # Prefer Pillow processing for reliable opacity and background removal
        try:
            from PIL import Image

            with Image.open(str(mun_logo)).convert('RGBA') as im:
                # Remove near-white backgrounds to reveal seal edges on white paper
                r, g, b, a = im.split()
                # Compute a mask of near-white pixels
                # Threshold: values > 245 (almost white)
                white_threshold = 245
                bg_mask = Image.eval(r, lambda x: 255 if x >= white_threshold else 0)
                bg_mask = Image.eval(Image.merge('RGB', (r, g, b)).convert('L'), lambda x: 255 if x >= white_threshold else 0)
                # Invert mask to keep non-white content
                keep_mask = Image.eval(bg_mask, lambda x: 0 if x > 0 else 255)
                # Combine with existing alpha if present
                if im.mode != 'RGBA':
                    a = Image.new('L', im.size, color=255)
                # Remove background
                a = Image.eval(a, lambda px: px)  # copy
                a.paste(0, mask=bg_mask)
                # Apply global fade
                fade = int(max(0, min(255, round(opacity * 255))))
                a = Image.eval(a, lambda px: int(px * (fade / 255.0)))
                im.putalpha(a)
                img = ImageReader(im)
                if logger:
                    logger.debug(f"Watermark prepared via Pillow: {mun_logo}")
        except Exception as pil_err:
            if logger:
                logger.debug(f"Watermark Pillow processing failed: {pil_err}")
            # Fallback: draw original image with canvas alpha (if available)
            img = ImageReader(str(mun_logo))

        c.saveState()
        c.translate(width / 2, height / 2)
        c.rotate(0)
        if hasattr(c, 'setFillAlpha'):
            c.setFillAlpha(opacity)
        size = size_mm * mm
        c.drawImage(img, -size / 2, -size / 2, width=size, height=size, preserveAspectRatio=True, mask='auto')
        c.restoreState()
    except Exception:
        # Silently ignore watermark failures to avoid blocking PDF generation
        pass
def _set_font(c: canvas.Canvas, name: str, size: int):
    """Set font with fallback to Helvetica family if Times is unavailable."""
    try:
        c.setFont(name, size)
    except Exception:
        # Fallback mappings
        fallback = {
            'Times-Roman': 'Helvetica',
            'Times-Bold': 'Helvetica-Bold',
            'Times-Italic': 'Helvetica-Oblique',
        }
        c.setFont(fallback.get(name, 'Helvetica'), size)



def generate_document_pdf(request, document_type, user, admin_user: Optional[object] = None) -> Tuple[Path, str]:
    """
    Generate a PDF for a document request and return (absolute_path, relative_path_from_upload_folder).
    """
    # Resolve basics
    municipality_name = getattr(getattr(request, 'municipality', None), 'name', '') or str(request.municipality_id)
    municipality_slug = _slugify(municipality_name)

    upload_base = Path(current_app.config.get('UPLOAD_FOLDER'))
    out_dir = upload_base / 'generated_docs' / municipality_slug
    _ensure_dir(out_dir)

    pdf_path = out_dir / f"{request.id}.pdf"

    # Resolve logos
    mun_logo, prov_logo = _resolve_logo_paths(municipality_name)
    # Debug logging to verify logo resolution
    try:
        if getattr(current_app, 'logger', None):
            current_app.logger.debug(f"PDF: municipality={municipality_name} mun_logo={mun_logo} prov_logo={prov_logo}")
    except Exception:
        pass

    # Prepare data context from request
    resident_full_name = ' '.join(
        filter(None, [getattr(user, 'first_name', None), getattr(user, 'last_name', None)])
    ) or getattr(user, 'username', 'Resident')

    issue_date = datetime.utcnow()

    # Load document type definitions
    doc_types = _load_document_types()
    code = (getattr(document_type, 'code', None) or getattr(document_type, 'name', 'generic')).lower()
    
    # Try multiple code variants to match config keys
    code_variants = [
        code,
        code.replace(' ', '_'),
        code.replace('_', ' '),
        code.replace('-', '_'),
    ]
    
    spec = None
    for variant in code_variants:
        if variant in doc_types:
            spec = doc_types[variant]
            break
    
    if not spec:
        spec = doc_types.get('generic') or {}
    
    level = (spec.get('level') or 'municipal').lower()
    
    # Debug logging
    try:
        print(f"[PDF DEBUG] doc_code='{code}' | variants={code_variants} | spec_found={spec is not None and spec != doc_types.get('generic')} | title={spec.get('title')}")
        if getattr(current_app, 'logger', None):
            current_app.logger.debug(f"PDF: doc_code={code} spec_found={spec is not None and spec != doc_types.get('generic')} title={spec.get('title')}")
    except Exception as e:
        print(f"[PDF DEBUG ERROR] {e}")

    # Derive effective content with precedence: admin_edited_content -> original columns -> resident_input
    import json as _json
    effective_purpose = None
    effective_remarks = None
    effective_civil = None
    effective_age = None
    try:
        edited = getattr(request, 'admin_edited_content', None) or {}
        if isinstance(edited, str):
            try:
                edited = _json.loads(edited)
            except Exception:
                edited = {}
        effective_purpose = (edited.get('purpose') if isinstance(edited, dict) else None) or getattr(request, 'purpose', None)
        effective_remarks = (edited.get('remarks') if isinstance(edited, dict) else None)
        effective_civil = (edited.get('civil_status') if isinstance(edited, dict) else None)
        try:
            ea = (edited.get('age') if isinstance(edited, dict) else None)
            if ea is not None:
                effective_age = int(ea)
        except Exception:
            pass
    except Exception:
        pass
    try:
        if effective_remarks is None:
            # Fallback to additional_notes string
            raw = getattr(request, 'additional_notes', None)
            if raw and isinstance(raw, str):
                # If legacy JSON was stored, try to parse and extract text
                if raw.strip().startswith('{'):
                    try:
                        parsed = _json.loads(raw)
                        if isinstance(parsed, dict):
                            effective_remarks = str(parsed.get('text') or '') or None
                            effective_civil = effective_civil or (str(parsed.get('civil_status')) if parsed.get('civil_status') else None)
                        else:
                            effective_remarks = raw
                    except Exception:
                        effective_remarks = raw
                else:
                    effective_remarks = raw
        # Fallback to resident_input
        ri = getattr(request, 'resident_input', None) or {}
        if isinstance(ri, str):
            try:
                ri = _json.loads(ri)
            except Exception:
                ri = {}
        if not effective_purpose:
            effective_purpose = (ri.get('purpose') if isinstance(ri, dict) else None) or getattr(request, 'purpose', '')
        if effective_remarks is None:
            effective_remarks = (ri.get('remarks') if isinstance(ri, dict) else None)
        if not effective_civil:
            effective_civil = (ri.get('civil_status') if isinstance(ri, dict) else None)
        if effective_age is None:
            try:
                ra = (ri.get('age') if isinstance(ri, dict) else None)
                if ra is not None:
                    effective_age = int(ra)
            except Exception:
                pass
    except Exception:
        pass

    ctx = {
        'residentName': resident_full_name,
        'resident_name': resident_full_name,
        'address': request.delivery_address or '',
        'municipality': municipality_name,
        'documentType': getattr(document_type, 'name', code),
        'purpose': effective_purpose or getattr(request, 'purpose', '') or '',
        'date': issue_date.strftime('%B %d, %Y'),
        'dateRequested': (request.created_at.strftime('%B %d, %Y') if getattr(request, 'created_at', None) else ''),
        'validity': '',
    }

    # Always use document type name from database as the title
    # This ensures the correct title appears even if config doesn't match
    doc_type_name = getattr(document_type, 'name', code)
    title = doc_type_name  # Use database name directly, ignore config title
    body = _simple_template(spec.get('body', ''), ctx)
    footer = _simple_template(spec.get('footer', ''), ctx)
    signatory = (spec.get('signatory') or {})

    # Render
    c = canvas.Canvas(str(pdf_path), pagesize=A4)

    # Border and watermark
    _draw_border(c)
    barangay_name = getattr(getattr(request, 'barangay', None), 'name', '')
    _draw_header(c, municipality_name, mun_logo, prov_logo, level=level, barangay_name=barangay_name)
    _draw_watermark(c, mun_logo)

    # Title
    width, height = A4
    _set_font(c, "Times-Bold", 18)
    c.drawCentredString(width / 2, height - 60 * mm, title.upper())

    # Body (formal paragraph with simple wrapping)
    def _wrap(text: str, max_chars: int = 95) -> list[str]:
        lines: list[str] = []
        for paragraph in (text or '').split('\n'):
            p = paragraph.strip()
            while len(p) > max_chars:
                split_at = p.rfind(' ', 0, max_chars)
                if split_at <= 0:
                    split_at = max_chars
                lines.append(p[:split_at].strip())
                p = p[split_at:].lstrip()
            if p:
                lines.append(p)
            lines.append('')
        return lines

    # Use effective remarks and civil status
    notes_text = str(effective_remarks or '').strip()
    civil_status = str(effective_civil or '').strip()

    opening = "TO WHOM IT MAY CONCERN:"
    age_phrase = (f"{effective_age} years old" if isinstance(effective_age, int) and effective_age > 0 else '')
    cs_phrase = civil_status
    combined_phrase = ''
    if age_phrase and cs_phrase:
        combined_phrase = f"{age_phrase}, {cs_phrase}"
    elif age_phrase:
        combined_phrase = age_phrase
    elif cs_phrase:
        combined_phrase = cs_phrase

    paragraph = (
        f"This is to certify that {resident_full_name}{(', ' + combined_phrase) if combined_phrase else ''}, "
        f"a bona fide resident of {('Barangay ' + barangay_name + ', ') if level=='barangay' and barangay_name else ''}"
        f"Municipality of {municipality_name}, Province of Zambales, has requested a "
        f"{getattr(document_type, 'name', code)} for the purpose of {ctx['purpose']}."
    )
    # Append remarks paragraph if provided
    extra = notes_text
    issued = (
        f"Issued this {ctx['date']} at the "
        f"{'Office of the Punong Barangay, Barangay ' + barangay_name if level=='barangay' else 'Office of the Municipal Mayor, Municipality of ' + municipality_name}, Province of Zambales."
    )

    text_obj = c.beginText(25 * mm, height - 82 * mm)
    text_obj.setFont("Times-Roman", 12)
    for line in [opening, "", *(_wrap(paragraph)), *( _wrap(extra) if extra else [] ), "", *(_wrap(issued))]:
        if line is None:
            continue
        text_obj.textLine(line)
    c.drawText(text_obj)

    # Signatory block (FOR/BY)
    _set_font(c, "Times-Roman", 12)
    official_title = 'Municipal Mayor' if level != 'barangay' else 'Punong Barangay'
    
    # Load municipality officials data
    officials = _load_municipality_officials()
    barangay_officials = _load_barangay_officials()
    mun_officials = officials.get(municipality_name, {})

    # Helper to normalize names for lookup (tolerate accents, punctuation, spacing)
    def _norm(s: str) -> str:
        try:
            import unicodedata as _ud
            s2 = _ud.normalize('NFKD', s or '')
            s2 = ''.join(ch for ch in s2 if not _ud.combining(ch))
        except Exception:
            s2 = (s or '')
        s2 = s2.strip().lower()
        # Remove punctuation we don't care about and unify spacing
        s2 = s2.replace('.', '').replace('-', ' ').replace('(', ' ').replace(')', ' ')
        # Normalize common variants: "(Pob.)" -> "poblacion"
        s2 = s2.replace(' pob ', ' poblacion ')
        s2 = s2.replace(' pob.', ' poblacion')
        s2 = s2.replace(' (pob) ', ' poblacion ')
        s2 = s2.replace(' (pob.) ', ' poblacion ')
        s2 = s2.replace('pob.', 'poblacion')
        while '  ' in s2:
            s2 = s2.replace('  ', ' ')
        return s2

    if level == 'barangay':
        # Prefer explicit Punong Barangay list by municipality + barangay
        pb_name = None
        try:
            muni_map = barangay_officials.get(municipality_name) or {}
            lookup = { _norm(k): v for k, v in muni_map.items() }
            pb_name = lookup.get(_norm(barangay_name))
        except Exception:
            pb_name = None
        # Fallback to municipalityOfficials.json if it contains punong_barangay
        official_name = pb_name or mun_officials.get('punong_barangay') or official_title
    else:
        # Municipal level uses mayor
        official_name = mun_officials.get('mayor') or official_title

    by_name = None
    if admin_user is not None:
        by_name = ' '.join(filter(None, [getattr(admin_user, 'first_name', None), getattr(admin_user, 'last_name', None)])) or getattr(admin_user, 'username', None)
    by_name = by_name or 'Municipal Records Officer'
    # Prefer actual admin user's role label when available
    by_role = None
    if admin_user is not None:
        try:
            admin_role = getattr(admin_user, 'role', None)
            if admin_role == 'admin':
                by_role = 'Admin'
            elif admin_role == 'municipal_admin':
                by_role = 'Municipal Admin'
        except Exception:
            by_role = None
    if not by_role:
        by_role = 'Municipal Admin' if level != 'barangay' else 'Barangay Admin'

    c.drawString(25 * mm, 42 * mm, f"FOR: {official_name}")
    c.drawString(25 * mm, 37 * mm, official_title)
    c.drawString(25 * mm, 30 * mm, f"BY: {by_name}")
    c.drawString(25 * mm, 25 * mm, by_role)

    # Footer note
    _set_font(c, "Times-Italic", 10)
    footer_text = footer or "This is a digitally issued document. No physical signature required. Generated via Munlink Zambales System."
    c.drawString(25 * mm, 20 * mm, footer_text)

    # Optional QR code (simple URL based on request number)
    try:
        from apps.api.utils.qr_generator import save_qr_code_file, generate_qr_code_data

        qr_dir = out_dir / "qr"
        _ensure_dir(qr_dir)
        qr_data = generate_qr_code_data(request)
        qr_file = qr_dir / f"{request.id}.png"
        save_qr_code_file(qr_data, str(qr_file))
        img = ImageReader(str(qr_file))
        # Increased QR size from 20mm to 35mm for better scannability
        qr_size = 35 * mm
        # Position QR at bottom-right, but shifted left to avoid overlapping blue border
        # Increased left margin from 10mm to 20mm to accommodate larger QR size
        c.drawImage(img, width - (qr_size + 20 * mm), 20 * mm, width=qr_size, height=qr_size, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass

    c.showPage()
    c.save()

    # Build relative path from UPLOAD_FOLDER for public URL
    rel_path = os.path.relpath(pdf_path, upload_base)
    # Normalize to POSIX-style for URLs
    rel_posix = rel_path.replace("\\", "/")
    return pdf_path, rel_posix


