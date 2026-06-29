import json

# Read the users backup with proper encoding
with open('users_backup.json', 'r', encoding='utf-8') as f:
    users = json.load(f)

print('📊 FIXING USERS BACKUP - Removing active_investments')
print('=' * 50)

# Fix all users - remove active_investments
fixed = 0
for user in users:
    if '✅' in user.get('active_investments', '0'):
        user['active_investments'] = '0'
        fixed += 1
        print(f'✅ Fixed {user.get("username")}: active_investments → 0')

# Save fixed file with proper encoding
with open('users_backup.json', 'w', encoding='utf-8') as f:
    json.dump(users, f, indent=2)

print(f'\n✅ Fixed {fixed} users')
print('✅ Updated users_backup.json')