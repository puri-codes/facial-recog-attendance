#!/usr/bin/env python
"""
Test the API endpoint from the Django shell.
Run with: python manage.py test_import_api
"""
from django.core.management.base import BaseCommand
from django.test import Client
from django.contrib.auth import get_user_model
import json

User = get_user_model()


class Command(BaseCommand):
    help = 'Test the student import API endpoint'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("\n" + "="*60))
        self.stdout.write(self.style.SUCCESS("Testing Student Import API Endpoint"))
        self.stdout.write(self.style.SUCCESS("="*60 + "\n"))
        
        # Get or create admin user
        admin_user = User.objects.filter(role='admin').first()
        if not admin_user:
            self.stdout.write(self.style.WARNING("Creating test admin user..."))
            admin_user = User.objects.create_user(
                username='testadmin_cmd',
                email='testadmin_cmd@local',
                password='testpass123',
                role='admin'
            )
        
        self.stdout.write(f"Using admin user: {admin_user.username}\n")
        
        # Make API request
        client = Client()
        client.force_login(admin_user)
        
        self.stdout.write("Making POST request to /api/import-students/...\n")
        
        try:
            response = client.post(
                '/api/import-students/',
                content_type='application/json'
            )
            
            self.stdout.write(f"Status Code: {response.status_code}\n")
            
            try:
                data = json.loads(response.content)
                self.stdout.write(f"Response:\n{json.dumps(data, indent=2)}\n")
                
                if response.status_code == 200 and data.get('success'):
                    results = data.get('results', {})
                    self.stdout.write(self.style.SUCCESS(
                        f"✓ Import successful!\n"
                        f"  Created: {results.get('created')}\n"
                        f"  Updated: {results.get('updated')}\n"
                        f"  Failed: {results.get('failed')}\n"
                        f"  Total: {results.get('total')}"
                    ))
                    
                    if results.get('errors'):
                        self.stdout.write(self.style.WARNING(
                            f"\nErrors ({len(results['errors'])}):"
                        ))
                        for error in results['errors'][:5]:
                            self.stdout.write(f"  - {error}")
                        if len(results['errors']) > 5:
                            self.stdout.write(f"  ... and {len(results['errors']) - 5} more")
                else:
                    self.stdout.write(self.style.ERROR(
                        f"❌ Request failed: {data.get('error', 'Unknown error')}"
                    ))
            except json.JSONDecodeError:
                self.stdout.write(f"Response (raw): {response.content[:500]}")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))
        
        self.stdout.write("\n" + "="*60 + "\n")
