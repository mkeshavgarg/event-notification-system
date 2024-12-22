# Security Policy

## Reporting Security Issues

**Do not report security vulnerabilities through public GitHub issues.**

Please report security vulnerabilities by emailing:
- Primary: security@your-domain.com
- Secondary: admin@your-domain.com

Include:
- Issue type (XSS, SQL injection, etc.)
- Full paths of affected files
- Steps to reproduce
- Potential impact
- Proof of concept (if possible)

## Token & Credentials Security

Store sensitive credentials using:
1. AWS Secrets Manager or AWS Parameter Store for production
2. HashiCorp Vault for enterprise deployments
3. Azure Key Vault for Microsoft Azure deployments
4. Environment variables (.env) for local development only

Current sensitive tokens in the codebase that need secure storage:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `SENDGRID_API_KEY`
- `APNS_KEY_ID`
- `APNS_TEAM_ID`
- `APNS_AUTH_KEY_PATH`

Never commit tokens, API keys, or credentials to version control.

## Security Best Practices

1. Keep dependencies updated
2. Enable 2FA for all team members
3. Regular security audits
4. Follow the principle of least privilege
5. Implement rate limiting
6. Use proper input validation
7. Enable audit logging

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Security Headers

Ensure all API endpoints implement:
- CORS policies
- CSP (Content Security Policy)
- HSTS (HTTP Strict Transport Security)
- XSS Protection headers
- Rate limiting headers

## Contact

For non-vulnerability related security questions:
security-team@your-domain.com
