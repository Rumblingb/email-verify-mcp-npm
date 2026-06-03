# @agentpay/email-verify-mcp

Email verification and validation for AI agents.

This npm package wraps the Python MCP server at [Rumblingb/email-verify-mcp](https://github.com/Rumblingb/email-verify-mcp).

## Install

```bash
npm install -g @agentpay/email-verify-mcp
pip install mcp
```

## Usage

```json
{
  "mcpServers": {
    "email-verify-mcp": {
      "command": "npx",
      "args": ["@agentpay/email-verify-mcp"]
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `verify_email` | Full email validation: format check, MX record lookup, disposable email detection, and typo suggestion. Returns a deliverability score from 0.0 to 1.0. |
| `verify_email_batch` | Batch verify multiple email addresses in one call. Accepts an array of emails, each counts as one call. |
| `is_disposable_email` | Check if a domain or email address belongs to a known disposable/temporary email provider. |

## Free Tier

50 lookups per server instance. No API key required.

## Pro Tier

Unlimited lookups — [Subscribe Pro $19/mo](https://buy.stripe.com/5kQ3cxflRabW9PW1AD1oI0r)

## About

Built by [AgentPay Labs](https://agentpay.so) — Governed payment middleware for AI agents.
