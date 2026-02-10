"""
Script de diagnóstico para verificar la configuración SMTP
"""

from mailing2fast_fastapi import settings

print("="*60)
print("Configuración SMTP Cargada")
print("="*60)

# Obtener cuenta default
default_account = settings.get_smtp_account("default")

print(f"\n📧 Cuenta DEFAULT:")
print(f"   Host: {default_account.host}")
print(f"   Puerto: {default_account.port}")
print(f"   Usuario: {default_account.username}")
print(f"   Seguridad: {default_account.security}")
print(f"   From Email: {default_account.from_email}")
print(f"   From Name: {default_account.from_name}")

print("\n" + "="*60)
print("Diagnóstico:")
print("="*60)

if default_account.port == 465 and default_account.security == "starttls":
    print("❌ ERROR: Puerto 465 requiere security='tls', no 'starttls'")
    print("   Cambia MAIL_SMTP_ACCOUNTS__DEFAULT__SECURITY=tls")
elif default_account.port == 587 and default_account.security == "tls":
    print("❌ ERROR: Puerto 587 requiere security='starttls', no 'tls'")
    print("   Cambia MAIL_SMTP_ACCOUNTS__DEFAULT__SECURITY=starttls")
elif default_account.port == 465 and default_account.security == "tls":
    print("✅ Configuración correcta para SSL/TLS (puerto 465)")
elif default_account.port == 587 and default_account.security == "starttls":
    print("✅ Configuración correcta para STARTTLS (puerto 587)")
else:
    print(f"⚠️  Configuración inusual: puerto {default_account.port} con {default_account.security}")

print("="*60)
