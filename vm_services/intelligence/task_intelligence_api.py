#!/usr/bin/env python3
"""
Task Intelligence API
Port: 8012

Provides automatic task extraction and management
for Transmogrifier mobile/desktop apps.

Integrates with existing intelligenceApi.ts:
- getPendingTasks()
- confirmTask(taskId)
- dismissTask(taskId)
- completeTask(taskId)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
from pathlib import Path

# Add intelligence modules to path
sys.path.insert(0, str(Path(__file__).parent))

from task_extractor import TaskExtractor

app = Flask(__name__)
CORS(app)

# Initialize service
task_service = TaskExtractor()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'task-intelligence',
        'port': 8012
    })


@app.route('/api/tasks/pending', methods=['GET'])
def get_pending_tasks():
    """
    Get pending tasks.
    
    Query params:
        limit: Max results (default: 50)
        min_confidence: Min confidence (default: 0.6)
    
    Returns:
        List of pending tasks
    """
    limit = int(request.args.get('limit', 50))
    min_confidence = float(request.args.get('min_confidence', 0.6))
    
    try:
        tasks = task_service.get_pending_tasks(
            limit=limit,
            min_confidence=min_confidence
        )
        
        # Format for mobile/desktop
        results = []
        for task in tasks:
            priority_label = {1: 'urgent', 2: 'high', 3: 'normal'}.get(task['priority'], 'low')
            
            results.append({
                'id': task['id'],
                'task_text': task['task_text'],
                'priority': task['priority'],
                'priority_label': priority_label,
                'deadline': task.get('deadline'),
                'source_email_id': task['source_email_id'],
                'source_email_subject': task['source_email_subject'],
                'confidence': task['confidence'],
                'status': task['status'],
                'created_at': task['created_at']
            })
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/confirm', methods=['POST'])
def confirm_task(task_id):
    """
    Confirm a task (user accepted it).
    
    Returns:
        Success status
    """
    try:
        result = task_service.confirm_task(task_id)
        
        if not result:
            return jsonify({'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'status': 'confirmed'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/dismiss', methods=['POST'])
def dismiss_task(task_id):
    """
    Dismiss a task (user rejected it).
    
    Returns:
        Success status
    """
    try:
        result = task_service.dismiss_task(task_id)
        
        if not result:
            return jsonify({'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'status': 'dismissed'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    """
    Mark task as complete.
    
    Returns:
        Success status
    """
    try:
        result = task_service.complete_task(task_id)
        
        if not result:
            return jsonify({'error': 'Task not found'}), 404
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'status': 'completed'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tasks/extract', methods=['POST'])
def extract_tasks():
    """
    Extract tasks from email.
    
    Request body:
        email_id: Email ID
        from: Sender email
        subject: Email subject
        body: Email body
    
    Returns:
        Extracted tasks
    """
    data = request.json
    
    if not data or 'email_id' not in data:
        return jsonify({'error': 'Email data required'}), 400
    
    try:
        email = {
            'id': data['email_id'],
            'from': data.get('from', ''),
            'subject': data.get('subject', ''),
            'body': data.get('body', '')
        }
        
        # Extract tasks
        tasks = task_service.extract_from_email(email)
        
        # Save to database
        saved = task_service.save_tasks(email['id'], email, tasks)
        
        # Format response
        results = []
        for task in tasks:
            results.append({
                'task_text': task.text,
                'priority': task.priority,
                'deadline': task.deadline.isoformat() if task.deadline else None,
                'confidence': task.confidence
            })
        
        return jsonify({
            'success': True,
            'extracted': len(tasks),
            'saved': saved,
            'tasks': results
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("Task Intelligence API starting on port 8012...")
    app.run(host='0.0.0.0', port=8012, debug=False)
