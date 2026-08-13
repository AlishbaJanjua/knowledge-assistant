import hashlib

from tenants.accounts import tenant_id_from_email


def get_tenant_id(email):
    """Legacy helper — same stable id used by accounts/uploads/Chroma/memory."""

    return tenant_id_from_email(email)
