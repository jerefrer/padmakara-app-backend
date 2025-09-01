# Amazon SES Email Configuration

This document describes how to configure Amazon Simple Email Service (SES) for production email sending in the Padmakara Buddhist learning platform.

## Overview

Amazon SES provides reliable, scalable email sending with excellent deliverability rates. The system has been configured to use SES in production while maintaining the browser-based email preview for development.

## Required AWS Setup

### 1. SES Service Setup

1. **Go to AWS SES Console**
   - Navigate to: https://console.aws.amazon.com/ses/
   - Select your preferred region (recommended: `us-east-1` or `eu-west-1`)

2. **Verify Your Domain**
   - Go to "Verified identities" → "Create identity"
   - Select "Domain" and enter your domain (e.g., `padmakara.pt`)
   - Add the provided DNS records to your domain
   - Wait for verification (can take up to 72 hours)

3. **Request Production Access**
   - By default, SES accounts are in "sandbox mode"
   - Go to "Account dashboard" → "Request production access"
   - Provide use case details for the Buddhist learning platform
   - Approval typically takes 24-48 hours

4. **Configure Sending Limits** (Optional)
   - Set daily sending quotas
   - Configure sending rate limits
   - Set up bounce and complaint handling

### 2. IAM User Setup

Create an IAM user specifically for SES email sending:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ses:SendEmail",
                "ses:SendRawEmail",
                "ses:GetSendQuota",
                "ses:GetSendStatistics",
                "ses:ListVerifiedEmailAddresses",
                "ses:GetIdentityVerificationAttributes"
            ],
            "Resource": "*"
        }
    ]
}
```

## Environment Configuration

### Required Variables for `.env.production`

Add these variables to your production environment file:

```bash
# Email Configuration
EMAIL_BACKEND=utils.ses_backends.SESEmailBackend
DEFAULT_FROM_EMAIL=noreply@padmakara.pt

# Amazon SES Configuration (separate from S3 credentials)
AWS_SES_ACCESS_KEY_ID=your_ses_access_key_here
AWS_SES_SECRET_ACCESS_KEY=your_ses_secret_key_here
AWS_SES_REGION_NAME=us-east-1

# Optional: SES Configuration Set (for tracking)
AWS_SES_CONFIGURATION_SET=padmakara-emails

# Site Configuration
SITE_NAME=Padmakara
FRONTEND_URL=https://app.padmakara.pt
BACKEND_URL=https://api.padmakara.pt
```

### Variable Descriptions

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `EMAIL_BACKEND` | Yes | Django email backend class | `utils.ses_backends.SESEmailBackend` |
| `DEFAULT_FROM_EMAIL` | Yes | Default sender email address | `noreply@padmakara.pt` |
| `AWS_SES_ACCESS_KEY_ID` | Yes | AWS access key for SES (separate from S3) | `AKIA...` |
| `AWS_SES_SECRET_ACCESS_KEY` | Yes | AWS secret key for SES (separate from S3) | `xyz123...` |
| `AWS_SES_REGION_NAME` | Yes | AWS region for SES | `us-east-1` |
| `AWS_SES_CONFIGURATION_SET` | No | SES config set for tracking | `padmakara-emails` |

## Email Backend Options

The system provides two SES email backends:

### 1. Standard SES Backend (Recommended)
```bash
EMAIL_BACKEND=utils.ses_backends.SESEmailBackend
```
- Supports HTML and plain text emails
- Optimized for better deliverability
- Handles most email use cases

### 2. SES Backend with Attachments
```bash
EMAIL_BACKEND=utils.ses_backends.SESEmailBackendWithAttachments
```
- Supports email attachments
- Uses raw email sending
- Slightly more complex processing

## Testing Configuration

### Command Line Testing

Test your SES configuration with the built-in management command:

```bash
# Basic test
python manage.py test_ses --to-email admin@padmakara.pt

# Test with domain verification check
python manage.py test_ses --to-email admin@padmakara.pt --check-domain padmakara.pt
```

### Expected Output

```
🔍 Testing Amazon SES Configuration...

1. Testing SES Client Initialization...
   Region: us-east-1
   Access Key: ✓ Set
   Secret Key: ✓ Set
   ✅ SES Client connected successfully!
   Daily sending quota: 200
   Emails sent today: 5
   Send rate per second: 1.0

2. Testing Domain Verification: padmakara.pt...
   ✅ Domain padmakara.pt is verified

3. Testing Email Sending to: admin@padmakara.pt...
   ✅ Test email sent successfully!
   Check admin@padmakara.pt for the test message

✅ SES testing completed!
```

## Email Templates

The system uses the following email templates (no changes needed):

- `templates/emails/magic_link_en.html` - English magic link emails
- `templates/emails/magic_link_pt.html` - Portuguese magic link emails
- `templates/emails/admin_approval_request.html` - Admin approval notifications

## Monitoring and Maintenance

### 1. SES Metrics

Monitor email sending through:
- AWS SES Console → "Reputation dashboard"
- Track bounces, complaints, and delivery rates
- Set up CloudWatch alarms for high bounce rates

### 2. Django Logging

Email sending is logged with these levels:
- `INFO`: Successful email sends
- `ERROR`: Failed email sends
- `WARNING`: Configuration issues

### 3. Error Handling

The SES backend handles common errors gracefully:
- Domain not verified: Logs error, continues operation
- Rate limiting: Built into SES service
- Invalid recipients: Logs specific failures

## Troubleshooting

### Common Issues

1. **Domain Not Verified**
   ```
   Error: MailFromDomainNotVerifiedException
   ```
   - Verify your domain in SES console
   - Check DNS records are correctly configured

2. **Sandbox Mode**
   ```
   Error: MessageRejected - Email address not verified
   ```
   - Request production access in SES console
   - Verify recipient emails in sandbox mode

3. **Rate Limiting**
   ```
   Error: Throttling - Maximum sending rate exceeded
   ```
   - Check your SES sending limits
   - Implement retry logic if needed

4. **Invalid Credentials**
   ```
   Error: NoCredentialsError
   ```
   - Verify AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
   - Check IAM user permissions

### Support Commands

```bash
# Check current email backend
python manage.py shell -c "from django.conf import settings; print(settings.EMAIL_BACKEND)"

# Send test magic link email
python manage.py shell -c "
from accounts.views import send_magic_link_email
from accounts.models import User
user = User.objects.get(email='admin@padmakara.pt')
send_magic_link_email(user, 'https://test-link.com', 'Test Device')
"

# Check SES sending statistics
python manage.py test_ses --to-email admin@padmakara.pt
```

## Production Deployment Checklist

- [ ] Domain verified in AWS SES
- [ ] Production access granted for SES account  
- [ ] IAM user created with SES permissions
- [ ] Environment variables configured in `.env.production`
- [ ] Test email sent successfully
- [ ] Email templates reviewed and localized
- [ ] Monitoring and alerting configured
- [ ] Bounce and complaint handling set up

## Security Considerations

1. **Credential Management**
   - Store AWS credentials securely
   - Use IAM roles when possible (EC2/ECS)
   - Rotate credentials regularly

2. **Email Security**
   - Enable SPF, DKIM, and DMARC records
   - Monitor reputation metrics
   - Handle bounces and complaints promptly

3. **Rate Limiting**
   - Respect SES sending limits
   - Implement queuing for bulk emails
   - Monitor sending patterns

## Cost Optimization

- SES charges $0.10 per 1,000 emails sent
- First 62,000 emails per month are free (if sent from EC2)
- Monitor costs through AWS billing dashboard
- Consider using SES configuration sets for detailed tracking