import json

# Read the users backup
with open('users_backup.json', 'r', encoding='utf-8') as f:
    users_data = json.load(f)

print('📊 CONVERTING USERS BACKUP TO DJANGO FIXTURE FORMAT')
print('=' * 50)

# Convert to Django fixture format
fixture = []
for user in users_data:
    # Skip empty users
    if user.get('username') == '-' or not user.get('username'):
        continue
    
    fixture.append({
        'model': 'auth.user',
        'pk': None,  # Let Django auto-assign
        'fields': {
            'username': user.get('username'),
            'first_name': user.get('full_name', '').split()[0] if user.get('full_name') and user.get('full_name') != '-' else '',
            'last_name': ' '.join(user.get('full_name', '').split()[1:]) if user.get('full_name') and user.get('full_name') != '-' and len(user.get('full_name', '').split()) > 1 else '',
            'email': '',
            'is_staff': False,
            'is_active': True,
            'is_superuser': False,
            'last_login': None,
            'date_joined': '2026-06-29T00:00:00Z'
        }
    })

# Save to fixture file
with open('users_fixture.json', 'w', encoding='utf-8') as f:
    json.dump(fixture, f, indent=2)

print(f'✅ Converted {len(fixture)} users to fixture format')
print('✅ Saved to users_fixture.json')