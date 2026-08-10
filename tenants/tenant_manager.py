import hashlib

def get_tenant_id(email):
    email = email.strip().lower()
    return hashlib.md5(email.encode()).hexdigest()