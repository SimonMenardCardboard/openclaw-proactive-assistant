#!/usr/bin/env python3
"""
Contact Intelligence API
Port: 8011

Provides contact search, VIP detection, and relationship management
for Transmogrifier mobile/desktop apps.

Integrates with existing intelligenceApi.ts:
- searchContacts(query)
- getVIPContacts()
- getContactDetails(contactId)
- getRelationshipScore(contactId)
- getFollowUpSuggestions()
- getTopRelationships()
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
from pathlib import Path

# Add intelligence modules to path
sys.path.insert(0, str(Path(__file__).parent))

from contact_unification import ContactUnification
from dynamic_relationship_scorer import DynamicRelationshipScorer

app = Flask(__name__)
CORS(app)

# Initialize services
contact_service = ContactUnification()
relationship_service = DynamicRelationshipScorer()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'contact-intelligence',
        'port': 8011
    })


@app.route('/api/contacts/search', methods=['GET'])
def search_contacts():
    """
    Search contacts by name or email.
    
    Query params:
        q: Search query (required)
        limit: Max results (default: 20)
    
    Returns:
        List of contacts with basic info
    """
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 20))
    
    if not query:
        return jsonify({'error': 'Query parameter required'}), 400
    
    try:
        contacts = contact_service.search_contacts(query, limit=limit)
        
        # Format for mobile/desktop
        results = []
        for contact in contacts:
            # Get relationship score if available
            score_data = relationship_service.get_relationship_score(contact['id'])
            
            results.append({
                'id': contact['id'],
                'name': contact['name'],
                'emails': contact['emails'],
                'company': contact.get('company'),
                'title': contact.get('title'),
                'importance_score': score_data.get('importance_score') if score_data else None,
                'last_contact': score_data.get('last_contact_date') if score_data else None,
                'vip': score_data.get('importance_score', 0) >= 70.0 if score_data else False
            })
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/contacts/vip', methods=['GET'])
def get_vip_contacts():
    """
    Get VIP contacts (importance >= 70).
    
    Query params:
        limit: Max results (default: 10)
    
    Returns:
        List of VIP contacts
    """
    limit = int(request.args.get('limit', 10))
    
    try:
        # Get top relationships
        top = relationship_service.get_top_relationships(limit=limit * 2)  # Get extra to filter
        
        # Filter for VIPs only
        vips = [r for r in top if r.get('importance_score', 0) >= 70.0][:limit]
        
        # Get contact details for each
        results = []
        for rel in vips:
            contact = contact_service.get_contact_by_email(rel['email'])
            if contact:
                results.append({
                    'id': contact['id'],
                    'name': contact['name'],
                    'emails': contact['emails'],
                    'company': contact.get('company'),
                    'title': contact.get('title'),
                    'importance_score': rel['importance_score'],
                    'last_contact': rel.get('last_contact_date'),
                    'vip': True
                })
        
        return jsonify(results)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/contacts/<int:contact_id>', methods=['GET'])
def get_contact(contact_id):
    """
    Get contact details by ID.
    
    Returns:
        Contact with relationship score
    """
    try:
        contact = contact_service.get_contact(contact_id)
        
        if not contact:
            return jsonify({'error': 'Contact not found'}), 404
        
        # Get relationship score
        score_data = relationship_service.get_relationship_score(contact_id)
        
        result = {
            'id': contact['id'],
            'name': contact['name'],
            'emails': contact['emails'],
            'company': contact.get('company'),
            'title': contact.get('title'),
            'importance_score': score_data.get('importance_score') if score_data else None,
            'last_contact': score_data.get('last_contact_date') if score_data else None,
            'vip': score_data.get('importance_score', 0) >= 70.0 if score_data else False
        }
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/relationships/<int:contact_id>', methods=['GET'])
def get_relationship_score(contact_id):
    """
    Get detailed relationship score for contact.
    
    Returns:
        Relationship metrics and scores
    """
    try:
        score = relationship_service.get_relationship_score(contact_id)
        
        if not score:
            return jsonify({'error': 'No relationship data'}), 404
        
        return jsonify(score)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/relationships/followups', methods=['GET'])
def get_followup_suggestions():
    """
    Get follow-up suggestions.
    
    Query params:
        days: Days threshold (default: 21)
        min_score: Min importance score (default: 50.0)
        limit: Max results (default: 10)
    
    Returns:
        List of suggested follow-ups
    """
    days = int(request.args.get('days', 21))
    min_score = float(request.args.get('min_score', 50.0))
    limit = int(request.args.get('limit', 10))
    
    try:
        suggestions = relationship_service.get_follow_up_suggestions(
            days_threshold=days,
            min_importance=min_score
        )
        
        # Limit results
        suggestions = suggestions[:limit]
        
        return jsonify(suggestions)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/relationships/top', methods=['GET'])
def get_top_relationships():
    """
    Get top relationships by importance.
    
    Query params:
        limit: Max results (default: 10)
    
    Returns:
        List of top relationships
    """
    limit = int(request.args.get('limit', 10))
    
    try:
        top = relationship_service.get_top_relationships(limit=limit)
        return jsonify(top)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("Contact Intelligence API starting on port 8011...")
    app.run(host='0.0.0.0', port=8011, debug=False)
