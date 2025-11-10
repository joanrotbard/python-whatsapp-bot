#!/usr/bin/env python3
"""Test script to verify webhook processing works."""
import logging
import sys
from app import create_app
from app.infrastructure.service_container import ServiceContainer

logging.basicConfig(level=logging.DEBUG)

# Sample webhook payload (adjust with your actual data)
SAMPLE_WEBHOOK = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "display_phone_number": "15550555555",
                    "phone_number_id": "PHONE_NUMBER_ID"
                },
                "contacts": [{
                    "profile": {
                        "name": "Test User"
                    },
                    "wa_id": "971559098067"  # Replace with your test number
                }],
                "messages": [{
                    "from": "971559098067",
                    "id": "wamid.test123",
                    "timestamp": "1234567890",
                    "text": {
                        "body": "Hello, this is a test message"
                    },
                    "type": "text"
                }]
            },
            "field": "messages"
        }]
    }]
}

def test_webhook_processing():
    """Test webhook message processing."""
    print("=" * 60)
    print("Testing Webhook Processing")
    print("=" * 60)
    
    try:
        # Create app
        print("\n1. Creating Flask app...")
        app = create_app()
        print("✓ App created")
        
        # Test service container
        print("\n2. Testing Service Container...")
        with app.app_context():
            container = app.config.get('service_container')
            if not container:
                print("✗ Service container not found in app.config")
                return False
            print("✓ Service container found")
            
            # Test message handler
            print("\n3. Testing Message Handler...")
            try:
                message_handler = container.get_message_handler()
                print("✓ Message handler created")
            except Exception as e:
                print(f"✗ Failed to create message handler: {e}")
                import traceback
                traceback.print_exc()
                return False
            
            # Test processing
            print("\n4. Processing test message...")
            try:
                message_handler.process_incoming_message(SAMPLE_WEBHOOK)
                print("✓ Message processed successfully")
                return True
            except Exception as e:
                print(f"✗ Failed to process message: {e}")
                import traceback
                traceback.print_exc()
                return False
                
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_webhook_processing()
    sys.exit(0 if success else 1)

