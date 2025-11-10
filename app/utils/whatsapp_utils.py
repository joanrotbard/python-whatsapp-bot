import logging
from flask import current_app, jsonify
import json
import requests

# from app.services.openai_service import generate_response
import re

from app.services.openai_service import generate_response


def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def get_text_message_input(recipient, text):
    """
    Get text message input for WhatsApp API.
    Recipient can be with or without + prefix - WhatsApp accepts both formats.
    """
    # Ensure recipient is a string and clean it
    recipient_str = str(recipient).strip()
    
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_str,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )


def get_typing_indicator_input(message_id):
    """
    Get typing indicator input for WhatsApp API.
    
    Format requires message_id, status="read", and typing_indicator with type="text"
    """
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {
            "type": "text"
        }
    }
    
    return json.dumps(payload)


def send_typing_indicator(message_id):
    """
    Send a typing indicator to show the user that the bot is processing their message.
    
    The indicator automatically stops after 25 seconds or when a message is sent.
    """
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    data = get_typing_indicator_input(message_id)
    
    # Log the payload being sent for debugging
    logging.info(f"Typing indicator payload: {data}")

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )
        
        # Check response status before raising
        if response.status_code >= 400:
            logging.error(f"HTTP error sending typing indicator")
            logging.error(f"Response status: {response.status_code}")
            logging.error(f"Response body: {response.text}")
            return None
        
        logging.info(f"Typing indicator sent successfully for message_id: {message_id}")
        log_http_response(response)
        return response
    except requests.Timeout:
        logging.error("Timeout occurred while sending typing indicator")
        return None
    except requests.RequestException as e:
        logging.error(f"Failed to send typing indicator: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Response status: {e.response.status_code}")
            logging.error(f"Response body: {e.response.text}")
        return None

def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )
        
        # Check response status before raising
        if response.status_code >= 400:
            error_msg = f"HTTP {response.status_code} error"
            try:
                error_body = response.json()
                error_msg = error_body.get('error', {}).get('message', error_msg)
            except:
                error_msg = response.text or error_msg
            
            logging.error(f"Failed to send message: {error_msg}")
            logging.error(f"Response status: {response.status_code}")
            logging.error(f"Response body: {response.text}")
            
            # Return the response object so caller can check status_code
            return response
        
        # Success - log and return response
        log_http_response(response)
        return response
        
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        # Return None to indicate failure, caller should handle
        return None
    except requests.RequestException as e:
        logging.error(f"Request failed due to: {e}")
        # Return None to indicate failure, caller should handle
        return None


def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text


def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    message_id = message["id"]  # Extract message_id for typing indicator
    message_body = message["text"]["body"]

    # Send typing indicator IMMEDIATELY to show the user we're processing
    logging.info(f"Received message from {wa_id} ({name}): {message_body}")
    logging.info(f"Sending typing indicator for message_id: {message_id}...")
    typing_result = send_typing_indicator(message_id)
    
    if typing_result:
        logging.info(f"✓ Typing indicator sent successfully to {wa_id}")
    else:
        logging.warning(f"⚠ Failed to send typing indicator to {wa_id}, but continuing with message processing")

    try:
        # OpenAI Integration - this takes a few seconds
        logging.info(f"Processing message with OpenAI for {wa_id}...")
        response = generate_response(message_body, wa_id, name)
        response = process_text_for_whatsapp(response)

        # Send the actual response (typing indicator will automatically stop when message is sent)
        logging.info(f"Sending response to {wa_id}...")
        data = get_text_message_input(wa_id, response)
        message_response = send_message(data)
        
        # Check if message was sent successfully
        if message_response is None:
            logging.error(f"✗ Failed to send response to {wa_id}: Connection error or timeout")
        elif hasattr(message_response, 'status_code'):
            if message_response.status_code == 200:
                logging.info(f"✓ Response sent successfully to {wa_id}")
            else:
                error_msg = f"HTTP {message_response.status_code}"
                error_code = None
                try:
                    error_data = message_response.json()
                    if 'error' in error_data:
                        error_msg = error_data['error'].get('message', error_msg)
                        error_code = error_data['error'].get('code')
                except:
                    error_msg = message_response.text or error_msg
                
                # Special handling for "not in allowed list" error
                if error_code == 131030 or 'not in allowed list' in error_msg.lower():
                    logging.error(f"✗ Failed to send response to {wa_id}: Number not in allowed list")
                    logging.error(f"  → The normalized number {wa_id} needs to be added to your allowed recipients list.")
                    logging.error(f"  → Go to Meta App Dashboard > WhatsApp > API Setup > 'To' field")
                    logging.error(f"  → Add the number: {wa_id}")
                    logging.error(f"  → Note: WhatsApp normalizes numbers, so use the exact format shown in the error")
                else:
                    logging.error(f"✗ Failed to send response to {wa_id}: {error_msg}")
        else:
            logging.warning(f"⚠ Unexpected response type when sending to {wa_id}")
            
    except Exception as e:
        logging.error(f"Error processing message for {wa_id}: {e}", exc_info=True)
        # Don't raise - we want to return success to WhatsApp even if processing fails
        # This prevents WhatsApp from retrying and spamming
        logging.error(f"Message processing failed, but returning success to WhatsApp to prevent retries")


def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )
