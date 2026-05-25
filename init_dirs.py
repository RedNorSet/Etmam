import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates', 'submissions')
os.makedirs(TEMPLATES_DIR, exist_ok=True)
print('✓ Created templates/submissions directory')

# Now create a simple test file to verify
with open(os.path.join(TEMPLATES_DIR, '_test.txt'), 'w') as f:
    f.write('test')
print('✓ Test file created successfully')
