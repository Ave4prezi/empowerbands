#!/usr/bin/env python3
"""
Apply activation update to empowerbands application
This script modifies app.py and templates/register.html to include:
- /add endpoint for adding unassigned bands
- /activate endpoint for full profile activation
"""

import os
import re

def update_app_py():
    """Update app.py to include activation and band routes"""
    app_py_path = 'app.py'
    
    if not os.path.exists(app_py_path):
        print(f"Error: {app_py_path} not found")
        return False
    
    with open(app_py_path, 'r') as f:
        content = f.read()
    
    # Add imports if not already present
    import_section = "from flask import Flask, render_template, request, jsonify\nfrom datetime import datetime"
    if "from flask import Flask" not in content:
        content = import_section + "\n\n" + content
    
    # Add route registrations
    activation_import = "from activation_routes import activation_bp"
    add_band_import = "from add_band_routes import add_band_bp"
    
    if activation_import not in content:
        # Find where to insert imports (after other imports)
        insert_pos = content.find('\n\n', content.find('from flask'))
        if insert_pos != -1:
            content = content[:insert_pos] + f"\n{activation_import}\n{add_band_import}" + content[insert_pos:]
    
    # Register blueprints
    register_activation = "app.register_blueprint(activation_bp)"
    register_add_band = "app.register_blueprint(add_band_bp)"
    
    if register_activation not in content:
        # Find where to insert blueprint registrations (before app.run or after app = Flask)
        app_run_pos = content.find('if __name__')
        if app_run_pos == -1:
            app_run_pos = len(content)
        
        blueprint_section = f"\n# Register blueprints\n{register_activation}\n{register_add_band}\n"
        content = content[:app_run_pos] + blueprint_section + content[app_run_pos:]
    
    with open(app_py_path, 'w') as f:
        f.write(content)
    
    print(f"✓ Updated {app_py_path}")
    return True

def update_register_html():
    """Update templates/register.html to include activation features"""
    html_path = 'templates/register.html'
    
    if not os.path.exists(html_path):
        print(f"Error: {html_path} not found")
        return False
    
    with open(html_path, 'r') as f:
        content = f.read()
    
    # Add activation section to the form
    activation_section = '''
    <div class="activation-section">
        <h3>Band Activation</h3>
        <div class="form-group">
            <label for="bands">Select Bands to Add:</label>
            <input type="text" id="bands" name="bands" placeholder="Enter band IDs (comma-separated)">
        </div>
        <button type="button" id="addBandsBtn" class="btn btn-secondary">Add Unassigned Bands</button>
        <button type="button" id="activateBtn" class="btn btn-primary">Activate Full Profile</button>
    </div>

    <script>
    document.getElementById('addBandsBtn').addEventListener('click', function() {
        const bands = document.getElementById('bands').value.split(',').map(b => b.trim());
        fetch('/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: '{{ user_id }}', band_ids: bands })
        })
        .then(r => r.json())
        .then(d => alert('Bands added: ' + d.message))
        .catch(e => alert('Error: ' + e));
    });

    document.getElementById('activateBtn').addEventListener('click', function() {
        const bands = document.getElementById('bands').value.split(',').map(b => b.trim());
        fetch('/activate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: '{{ user_id }}', bands: bands })
        })
        .then(r => r.json())
        .then(d => alert('Profile activated: ' + d.message))
        .catch(e => alert('Error: ' + e));
    });
    </script>
    '''
    
    # Insert before closing form tag or at end of body
    if '</form>' in content:
        content = content.replace('</form>', activation_section + '</form>')
    else:
        content += activation_section
    
    with open(html_path, 'w') as f:
        f.write(content)
    
    print(f"✓ Updated {html_path}")
    return True

def main():
    """Main function to apply all updates"""
    print("Applying activation update to empowerbands...")
    
    success = True
    success = update_app_py() and success
    success = update_register_html() and success
    
    if success:
        print("\n✓ Activation update applied successfully!")
        return 0
    else:
        print("\n✗ Activation update encountered errors")
        return 1

if __name__ == '__main__':
    exit(main())