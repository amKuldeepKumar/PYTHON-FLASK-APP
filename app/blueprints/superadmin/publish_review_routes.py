from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import bp
from ...models.user import Role
from ...rbac import require_role
from ...services.publish_review_service import PublishReviewService

REVIEW_ROLE_CODES = (Role.SUPERADMIN.value, Role.EDITOR.value)


def _can_publish() -> bool:
    return (getattr(current_user, 'role_code', '') or '').strip().upper() == Role.SUPERADMIN.value


@bp.get('/review-dashboard')
@login_required
@require_role(*REVIEW_ROLE_CODES)
def review_dashboard():
    module = (request.args.get('module') or 'all').strip().lower()
    state = (request.args.get('state') or 'all').strip().lower()
    rows = PublishReviewService.dashboard_rows(module=module, state=state)
    return render_template(
        'superadmin/review_dashboard.html',
        rows=rows,
        module=module,
        state=state,
        counts=PublishReviewService.dashboard_counts(),
        can_publish=_can_publish(),
    )


@bp.post('/review-dashboard/action')
@login_required
@require_role(*REVIEW_ROLE_CODES)
def review_dashboard_action():
    item_type = (request.form.get('item_type') or '').strip()
    item_id = request.form.get('item_id', type=int) or 0
    action = (request.form.get('action') or '').strip().lower()
    note = (request.form.get('note') or '').strip() or None
    if action in {'approve', 'publish', 'reject', 'unpublish'} and not _can_publish():
        flash('Only Superadmin can approve, reject, publish, or unpublish content.', 'warning')
        return redirect(request.referrer or url_for('superadmin.review_dashboard'))
    ok, message = PublishReviewService.apply_action(item_type, item_id, action, note)
    flash(message, 'success' if ok else 'warning')
    return redirect(request.referrer or url_for('superadmin.review_dashboard'))


@bp.post('/review-dashboard/bulk')
@login_required
@require_role(*REVIEW_ROLE_CODES)
def review_dashboard_bulk():
    action = (request.form.get('bulk_action') or '').strip().lower()
    note = (request.form.get('bulk_note') or '').strip() or None
    raw_items = request.form.getlist('selected_items')
    if action in {'approve', 'publish', 'reject', 'unpublish'} and not _can_publish():
        flash('Only Superadmin can run this bulk action.', 'warning')
        return redirect(request.referrer or url_for('superadmin.review_dashboard'))
    processed = 0
    failed = 0
    for raw in raw_items:
        try:
            item_type, item_id_text = raw.split(':', 1)
            item_id = int(item_id_text)
        except Exception:
            failed += 1
            continue
        ok, _message = PublishReviewService.apply_action(item_type, item_id, action, note)
        if ok:
            processed += 1
        else:
            failed += 1
    if processed:
        flash(f'Bulk action completed for {processed} item(s).', 'success')
    if failed:
        flash(f'{failed} item(s) could not be updated.', 'warning')
    return redirect(request.referrer or url_for('superadmin.review_dashboard'))
