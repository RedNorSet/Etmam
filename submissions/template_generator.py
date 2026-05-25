"""Auto-create submission templates on app initialization"""
import os
from pathlib import Path

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Template directories
PROJECT_TEMPLATES_DIR = BASE_DIR / 'templates' / 'submissions'
APP_TEMPLATES_DIR = BASE_DIR / 'submissions' / 'templates' / 'submissions'

# Create directories
for template_dir in [PROJECT_TEMPLATES_DIR, APP_TEMPLATES_DIR]:
    template_dir.mkdir(parents=True, exist_ok=True)

# Milestone List Template
MILESTONE_LIST = '''{% extends 'base.html' %}
{% block title %}Milestones - Submissions{% endblock %}
{% block content %}
<div style="display:flex;min-height:100vh;background:#f0f4f8">
<aside style="width:280px;background:#1e2433;color:#f1f5f9;padding:24px 20px;overflow-y:auto;border-right:1px solid rgba(255,255,255,.1)">
<div style="margin-bottom:32px"><h2 style="font-size:20px;font-weight:600;margin:0 0 8px 0">{{ project.team.name }}</h2><p style="font-size:13px;color:#cbd5e1;margin:0">Project: {{ project.title }}</p></div>
<nav style="display:flex;flex-direction:column;gap:8px">
<a href="{% url 'dashboard:student' %}" style="padding:10px 12px;border-radius:6px;color:#cbd5e1;text-decoration:none;font-size:14px">📊 Dashboard</a>
<a href="{% url 'submissions:milestone_list' %}" style="padding:10px 12px;border-radius:6px;background:rgba(59,130,246,0.1);color:#60a5fa;text-decoration:none;font-size:14px;font-weight:500">📋 Milestones</a>
</nav>
</aside>
<main style="flex:1;padding:32px"><div style="max-width:1000px"><h1 style="font-size:28px;font-weight:600;margin:0 0 8px 0;color:#1e293b">Milestones</h1><p style="color:#64748b;margin:0 0 24px 0">Submit your project deliverables</p>
{% if milestones %}
<div style="display:grid;gap:16px">{% for milestone in milestones %}
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px"><div style="display:flex;justify-content:space-between;align-items:flex-start;gap:16px"><div style="flex:1"><h3 style="font-size:18px;font-weight:600;margin:0;color:#1e293b">{{ milestone.title }}</h3>
{% if milestone.description %}<p style="color:#64748b;font-size:14px;margin:8px 0">{{ milestone.description }}</p>{% endif %}
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:12px">
<div><p style="font-size:12px;color:#94a3b8;margin:0 0 4px 0;font-weight:500">Due Date</p><p style="font-size:14px;color:#1e293b;margin:0;font-weight:500">{{ milestone.due_date|date:'M d, Y' }}</p></div>
<div><p style="font-size:12px;color:#94a3b8;margin:0 0 4px 0;font-weight:500">Type</p><p style="font-size:14px;color:#1e293b;margin:0;font-weight:500">{{ milestone.get_type_display }}</p></div>
</div></div>
<a href="{% url 'submissions:milestone_detail' milestone.id %}" style="display:inline-block;padding:10px 20px;background:#3b82f6;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;font-weight:500;white-space:nowrap">→ Submit</a></div></div>{% endfor %}</div>
{% else %}
<div style="text-align:center;padding:48px;background:#fff;border-radius:12px;border:2px dashed #e2e8f0"><p style="color:#64748b">No milestones available</p></div>
{% endif %}
</div></main></div>
{% endblock %}'''

MILESTONE_DETAIL = '''{% extends 'base.html' %}
{% block title %}{{ milestone.title }} - Submit{% endblock %}
{% block content %}
<div style="display:flex;min-height:100vh;background:#f0f4f8">
<aside style="width:280px;background:#1e2433;color:#f1f5f9;padding:24px 20px;overflow-y:auto;border-right:1px solid rgba(255,255,255,.1)">
<div style="margin-bottom:32px"><h2 style="font-size:20px;font-weight:600;margin:0">{{ milestone.project.team.name }}</h2></div>
<nav style="display:flex;flex-direction:column;gap:8px">
<a href="{% url 'dashboard:student' %}" style="padding:10px 12px;border-radius:6px;color:#cbd5e1;text-decoration:none;font-size:14px">📊 Dashboard</a>
<a href="{% url 'submissions:milestone_list' %}" style="padding:10px 12px;border-radius:6px;color:#cbd5e1;text-decoration:none;font-size:14px">📋 Milestones</a>
</nav>
</aside>
<main style="flex:1;padding:32px"><div style="max-width:900px"><h1 style="font-size:28px;font-weight:600;margin:0;color:#1e293b">{{ milestone.title }}</h1>
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin:20px 0">
<p><strong>Supervisor:</strong> {{ milestone.project.supervisor.full_name }}</p>
<p><strong>Due:</strong> {{ milestone.due_date|date:'M d, Y' }}</p>
{% if milestone.description %}<p>{{ milestone.description }}</p>{% endif %}
</div>
<form method="post" enctype="multipart/form-data" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px">
{% csrf_token %}
<label style="display:block;font-weight:600;margin:0 0 8px 0">Upload Files *</label>
<input type="file" name="files" multiple required style="width:100%;padding:10px;border:1px solid #e2e8f0;border-radius:6px;margin-bottom:20px"/>
<label style="display:block;font-weight:600;margin:0 0 8px 0">Notes</label>
<textarea name="notes" style="width:100%;padding:10px;border:1px solid #e2e8f0;border-radius:6px;margin-bottom:20px;min-height:100px"></textarea>
<button type="submit" style="padding:10px 24px;background:#3b82f6;color:#fff;border:none;border-radius:6px;font-weight:600;cursor:pointer">Submit</button>
</form>
</div></main></div>
{% endblock %}'''

SUBMISSION_LIST = '''{% extends 'base.html' %}
{% block title %}Submissions Review{% endblock %}
{% block content %}
<div style="display:flex;min-height:100vh;background:#f0f4f8">
<aside style="width:280px;background:#1e2433;color:#f1f5f9;padding:24px 20px;overflow-y:auto;border-right:1px solid rgba(255,255,255,.1)">
<div style="margin-bottom:32px"><h2 style="font-size:20px;font-weight:600;margin:0">Submissions</h2></div>
<nav style="display:flex;flex-direction:column;gap:8px">
<a href="{% url 'dashboard:supervisor' %}" style="padding:10px 12px;border-radius:6px;color:#cbd5e1;text-decoration:none;font-size:14px">📊 Dashboard</a>
<a href="{% url 'submissions:submission_list' %}" style="padding:10px 12px;border-radius:6px;background:rgba(59,130,246,0.1);color:#60a5fa;text-decoration:none;font-size:14px;font-weight:500">📋 Submissions</a>
</nav>
</aside>
<main style="flex:1;padding:32px"><div style="max-width:1200px"><h1 style="font-size:28px;font-weight:600;margin:0;color:#1e293b">Submissions Review</h1>
<p style="color:#64748b;margin:0 0 24px 0">Review and grade submissions</p>
{% if submissions %}
<div style="display:grid;gap:16px">{% for submission in submissions %}
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px"><div style="display:flex;justify-content:space-between;align-items:flex-start">
<div><h3 style="margin:0;color:#1e293b">{{ submission.milestone.title }}</h3><p style="color:#64748b;font-size:13px;margin:8px 0">Team: {{ submission.milestone.project.team.name }} | v{{ submission.version }}</p></div>
<a href="{% url 'submissions:submission_detail' submission.id %}" style="padding:10px 20px;background:#3b82f6;color:#fff;text-decoration:none;border-radius:6px;font-weight:500;white-space:nowrap">Review →</a>
</div></div>{% endfor %}</div>
{% else %}<div style="text-align:center;padding:48px;background:#fff;border-radius:12px;border:2px dashed #e2e8f0"><p style="color:#64748b">No submissions yet</p></div>
{% endif %}
</div></main></div>
{% endblock %}'''

SUBMISSION_DETAIL = '''{% extends 'base.html' %}
{% block title %}Grade {{ submission.milestone.title }}{% endblock %}
{% block content %}
<div style="display:flex;min-height:100vh;background:#f0f4f8">
<aside style="width:280px;background:#1e2433;color:#f1f5f9;padding:24px 20px;overflow-y:auto;border-right:1px solid rgba(255,255,255,.1)">
<div style="margin-bottom:32px"><h2 style="font-size:20px;font-weight:600;margin:0">Submissions</h2></div>
<nav style="display:flex;flex-direction:column;gap:8px">
<a href="{% url 'dashboard:supervisor' %}" style="padding:10px 12px;border-radius:6px;color:#cbd5e1;text-decoration:none;font-size:14px">📊 Dashboard</a>
<a href="{% url 'submissions:submission_list' %}" style="padding:10px 12px;border-radius:6px;color:#cbd5e1;text-decoration:none;font-size:14px">📋 Submissions</a>
</nav>
</aside>
<main style="flex:1;padding:32px"><div style="max-width:900px"><h1 style="font-size:28px;font-weight:600;margin:0;color:#1e293b">{{ submission.milestone.title }}</h1>
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin:20px 0">
<p><strong>Team:</strong> {{ submission.milestone.project.team.name }}</p>
<p><strong>Submitted by:</strong> {{ submission.submitted_by.full_name }}</p>
<p><strong>Version:</strong> {{ submission.version }}</p>
<p><strong>Date:</strong> {{ submission.submitted_at|date:'M d, Y H:i' }}</p>
</div>
{% if submission.files.all %}
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin:20px 0">
<h3 style="margin-top:0">Files</h3>
{% for file in submission.files.all %}
<div style="display:flex;justify-content:space-between;padding:10px;background:#f8fafc;border-radius:6px;margin-bottom:8px">
<span>📄 {{ file.file_name }}</span>
<a href="{% url 'submissions:download_file' file.id %}" style="padding:6px 12px;background:#3b82f6;color:#fff;text-decoration:none;border-radius:4px;font-size:13px">⬇ Download</a>
</div>
{% endfor %}
</div>
{% endif %}
<form method="post" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:24px">
{% csrf_token %}
<label style="display:block;font-weight:600;margin:0 0 8px 0">Score (0-100) *</label>
<input type="number" name="score" min="0" max="100" step="0.1" required style="width:100%;padding:10px;border:1px solid #e2e8f0;border-radius:6px;margin-bottom:20px"/>
<label style="display:block;font-weight:600;margin:0 0 8px 0">Feedback</label>
<textarea name="feedback" style="width:100%;padding:10px;border:1px solid #e2e8f0;border-radius:6px;margin-bottom:20px;min-height:120px"></textarea>
<button type="submit" style="padding:10px 24px;background:#3b82f6;color:#fff;border:none;border-radius:6px;font-weight:600;cursor:pointer">Submit Grade</button>
</form>
</div></main></div>
{% endblock %}'''

# Write templates
templates = {
    'milestone_list.html': MILESTONE_LIST,
    'milestone_detail.html': MILESTONE_DETAIL,
    'submission_list.html': SUBMISSION_LIST,
    'submission_detail.html': SUBMISSION_DETAIL,
}

try:
    for filename, content in templates.items():
        # Write to project templates
        project_file = PROJECT_TEMPLATES_DIR / filename
        with open(project_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Write to app templates
        app_file = APP_TEMPLATES_DIR / filename
        with open(app_file, 'w', encoding='utf-8') as f:
            f.write(content)
except Exception as e:
    pass  # Silently fail during import
