"""Deterministic specifications for isolated tests only."""
from app.models.application import ApplicationSpec


def specification():
    return ApplicationSpec.model_validate({
        'name': 'Recruitment workspace', 'description': 'Manage companies and candidates.', 'language': 'en',
        'roles': ['admin', 'recruiter', 'viewer'], 'entities': [
            {'name': 'companies', 'label': 'Companies', 'fields': [{'name': 'name', 'label': 'Company name', 'required': True}],
             'read_roles': ['admin', 'recruiter', 'viewer'], 'write_roles': ['admin', 'recruiter'], 'requirement_ids': ['R1']},
            {'name': 'candidates', 'label': 'Candidates', 'fields': [
                {'name': 'name', 'label': 'Candidate name', 'required': True},
                {'name': 'email', 'label': 'Email', 'kind': 'email'},
                {'name': 'company', 'label': 'Company', 'kind': 'reference', 'reference': 'companies'},
                {'name': 'stage', 'label': 'Stage', 'kind': 'select', 'options': ['new', 'interview', 'hired'], 'required': True}],
             'read_roles': ['admin', 'recruiter', 'viewer'], 'write_roles': ['admin', 'recruiter'], 'requirement_ids': ['R2'],
             'transitions': [{'label': 'Schedule interview', 'field': 'stage', 'from_value': 'new', 'to_value': 'interview', 'roles': ['admin', 'recruiter']}]}
        ], 'requirements': [
            {'id': 'R1', 'description': 'Company records', 'evidence': 'User requested company records.', 'implementation': 'supported'},
            {'id': 'R2', 'description': 'Candidate records and interview status', 'evidence': 'User request.', 'implementation': 'supported'}],
        'assumptions': ['One team per application.'], 'limitations': ['No calendar integration.'], 'change_summary': 'Initial draft.'
    }).model_dump()

