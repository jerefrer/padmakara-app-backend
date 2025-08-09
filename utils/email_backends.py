import os
import tempfile
import webbrowser
from datetime import datetime
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings


class BrowserEmailBackend(BaseEmailBackend):
    """
    Email backend that opens emails in the default web browser for development.
    Perfect for previewing magic link emails during development.
    """
    
    def send_messages(self, email_messages):
        """
        Send a list of email messages by opening them in the browser.
        """
        if not email_messages:
            return 0
        
        msg_count = 0
        for message in email_messages:
            try:
                self._send_message(message)
                msg_count += 1
            except Exception as e:
                if not self.fail_silently:
                    raise e
        
        return msg_count
    
    def _send_message(self, message):
        """
        Create an HTML file and open it in the browser.
        """
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"email_{timestamp}_{id(message)}.html"
        file_path = os.path.join(tempfile.gettempdir(), filename)
        
        # Create HTML content
        html_content = self._create_html_content(message)
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Open in browser
        webbrowser.open(f'file://{file_path}')
        
        print(f"📧 Email opened in browser: {message.subject}")
        print(f"   To: {', '.join(message.to)}")
        print(f"   File: {file_path}")
    
    def _create_html_content(self, message):
        """
        Create a complete HTML document for the email.
        """
        # Get email content
        html_body = ""
        text_body = ""
        
        if hasattr(message, 'alternatives') and message.alternatives:
            # Check for HTML version
            for content, content_type in message.alternatives:
                if content_type == 'text/html':
                    html_body = content
                    break
        
        if not html_body:
            # Use plain text and convert to HTML
            text_body = message.body
            html_body = f"<pre style='white-space: pre-wrap; font-family: Arial, sans-serif;'>{text_body}</pre>"
        
        # Create complete HTML document
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Preview: {message.subject}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .email-header {{
            background-color: #2c3e50;
            color: white;
            padding: 15px;
            border-radius: 5px 5px 0 0;
            margin-bottom: 0;
        }}
        .email-header h1 {{
            margin: 0 0 10px 0;
            font-size: 18px;
        }}
        .email-meta {{
            font-size: 12px;
            opacity: 0.9;
        }}
        .email-content {{
            background-color: white;
            padding: 20px;
            border-radius: 0 0 5px 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            min-height: 200px;
        }}
        .dev-notice {{
            background-color: #e74c3c;
            color: white;
            padding: 10px;
            text-align: center;
            font-weight: bold;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .magic-link {{
            display: inline-block;
            padding: 10px 20px;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .magic-link:hover {{
            background-color: #2980b9;
        }}
    </style>
</head>
<body>
    <div class="dev-notice">
        🚀 DEVELOPMENT EMAIL PREVIEW - This email would be sent to: {', '.join(message.to)}
    </div>
    
    <div class="email-header">
        <h1>📧 {message.subject}</h1>
        <div class="email-meta">
            <strong>From:</strong> {message.from_email}<br>
            <strong>To:</strong> {', '.join(message.to)}<br>
            <strong>Date:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>
    
    <div class="email-content">
        {html_body}
    </div>
    
    <script>
        // Add click handlers to magic links
        document.addEventListener('DOMContentLoaded', function() {{
            const links = document.querySelectorAll('a[href*="/activate/"]');
            links.forEach(link => {{
                link.addEventListener('click', function(e) {{
                    e.preventDefault();
                    const href = this.href;
                    if (confirm('Open magic link in new tab?\\n\\n' + href)) {{
                        window.open(href, '_blank');
                    }}
                }});
            }});
        }});
    </script>
</body>
</html>
        """
        
        return html_template