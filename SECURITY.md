# Security Policy

## Supported Versions

Only the latest major version of Agent Pump (currently v1.0.0) receives security updates and bug fixes. Previous major versions may receive critical security fixes only.

## Reporting a Vulnerability

If you discover a security vulnerability, please **DO NOT** open a public issue. Instead, please send an email privately to the maintainers.

### Contact Information

- **Email**: david.burhans@gmail.com
- **Project**: Agent Pump

### What to Include

When reporting a vulnerability, please include:

1. **Description**: A clear description of the vulnerability
2. **Impact**: Potential impact of the vulnerability
3. **Steps to Reproduce**: Detailed steps to reproduce the issue
4. **Affected Versions**: Which versions of Agent Pump are affected
5. **Fix Suggestion** (optional): Any suggested fix or mitigation

### What to Expect

- We will acknowledge receipt of your report within 48 hours
- We will provide a detailed response within 7 days
- If confirmed, we will work on a fix and provide an estimated timeline
- Credit for the discovery will be included in the release notes if desired

## Security Best Practices

### For Users

1. **API Keys**: Never commit API keys to version control
   - Use environment variables: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
   - Or use the `~/.config/agent-pump/config.yml` file (not committed to git)
   - Add `.agent-pump/` to `.gitignore`

2. **GitHub Tokens**: Use personal access tokens with minimal permissions
   - Grant only `repo` scope if not using GitHub Actions
   - Revoke tokens when no longer needed
   - Use fine-grained tokens when possible

3. **Code Review**: Review AI-generated code before committing
   - Agent Pump can write code, but review is recommended
   - Use the "brainstorm" phase to review changes
   - Enable dry-run mode for preview: `--dry-run`

4. **Isolation**: Run Agent Pump in isolated environments when possible
   - Use containerization for critical production codebases
   - Test changes in feature branches before merging

### For Developers

1. **Dependency Management**
   - Keep dependencies up to date: `uv sync --upgrade`
   - Review security advisories for dependencies regularly
   - Use `pip-audit` or similar tools

2. **Secrets Management**
   - Never log secrets or tokens
   - Use `python-dotenv` for environment variable management
   - Implement secret scanning in CI/CD pipelines

3. **Input Validation**
   - Validate all user inputs
   - Sanitize file paths to prevent path traversal
   - Validate configuration files

4. **Rate Limiting**
   - Implement rate limiting on API endpoints
   - Use timeouts for external API calls
   - Monitor for abuse patterns

## Known Security Considerations

### AI Backend Integration

Agent Pump integrates with third-party AI backends. Considerations:

- **Code Execution**: AI backends may execute generated code in dry-run mode
- **Data Privacy**: Code snippets are sent to AI backends for processing
- **Model Updates**: Backend behavior may change with model updates

**Mitigation**: Review dry-run output, use local backends when possible, and configure backend settings appropriately.

### Web API

The HTTP API and WebSocket endpoints support authentication:

- **API Key Authentication**: Optional API key protection for web interface
- **No Default Credentials**: No default passwords or keys are included
- **WebSocket Security**: Secure WebSocket connections require authentication when enabled

**Recommendation**: Always use API key authentication when exposing the web interface.

### Git Operations

Agent Pump performs automated git operations:

- **Branch Creation**: Creates feature branches automatically
- **Commit Messages**: Generates commits with AI-authored messages
- **Push Operations**: May push to remote if configured

**Mitigation**: Review all commits, use branch protection rules, and enable required reviews.

## Security Updates

### Version Information

Security updates will be announced via:

- GitHub Releases: Check for new versions tagged with security fixes
- CHANGELOG.md: Security fixes are documented
- GitHub Security Advisories: Critical vulnerabilities are published

### Update Process

1. Review the security advisory
2. Update to the latest version: `uv sync --upgrade`
3. Review and apply configuration changes if needed
4. Review any generated code after the update

## Responsible Disclosure

We follow **Responsible Disclosure** principles:

- Give vendors reasonable time to fix vulnerabilities
- Work with vendors to understand and fix issues
- Disclose responsibly with coordinated timelines
- Prioritize user safety and data protection

## License

Agent Pump is released under the MIT License. See [LICENSE](LICENSE) for details.

## Additional Resources

- [GitHub Security](https://docs.github.com/en/code-security/security-advisories)
- [OWASP Guidelines](https://owasp.org/www-project-secure-software-development-lifecycle-guide)
- [CWE Top 25](https://cwe.mitre.org/top25)
