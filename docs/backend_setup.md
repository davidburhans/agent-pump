# Backend Setup Guide

Agent Pump supports multiple AI backends for code generation and analysis. This guide covers setup for each supported backend.

## Table of Contents

- [Supported Backends](#supported-backends)
- [Gemini](#gemini)
- [Qwen](#qwen)
- [Claude Code](#claude-code-beta)
- [OpenCode](#opencode-beta)
- [Pi Coding Agent](#pi-coding-agent)
- [Dry Run](#dry-run)
- [Fallback Chains](#fallback-chains)
- [Troubleshooting](#troubleshooting)

## Supported Backends

| Backend | Status | API Provider | Context Window |
|---------|--------|--------------|----------------|
| Gemini | ✅ Production Ready | Google | 1M tokens |
| Qwen | ✅ Production Ready | Alibaba Cloud | 32K tokens |
| Claude Code | ⚠️ Beta | Anthropic | 200K tokens |
| OpenCode | ⚠️ Beta | OpenCode.ai | Varies |
| Pi Coding Agent | ⚠️ Beta | Multi (Extensible) | 128K+ tokens |
| Dry Run | ✅ Always Available | N/A (Mock) | N/A |

## Gemini

Gemini is the recommended backend and has the best integration with Agent Pump.

### Prerequisites

```bash
# Install gemini-cli
uv pip install gemini-cli

# Or install globally
pip install gemini-cli
```

### Configuration

**Option 1: Environment Variables**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

**Option 2: Configuration File**
Add to `~/.config/agent-pump/config.yml` or `.agent-pump/config.yml`:
```yaml
backends:
  default: gemini
  gemini:
    model: gemini-2.5-pro
    temperature: 0.7
```

### Setup Verification

```bash
# Test Gemini CLI
gemini-cli "Hello, world!"

# Test with Agent Pump
uv run agent-pump ask "What is 2+2?" ./your-project
```

### Models

- `gemini-2.5-pro` - Recommended (best performance)
- `gemini-2.5-flash` - Faster, good for code generation
- `gemini-2.0-pro` - Previous generation, stable
- `gemini-1.5-pro` - For simpler tasks

See [Google AI Models](https://ai.google.dev/gemini-api/docs/models) for details.

## Qwen

Qwen from Alibaba Cloud provides excellent code generation capabilities.

### Prerequisites

```bash
# No additional CLI tools required
pip install dashscope
```

### Configuration

**Option 1: Environment Variables**
```bash
export DASHSCOPE_API_KEY="your-api-key-here"
```

**Option 2: Configuration File**
```yaml
backends:
  qwen:
    model: qwen-turbo
    temperature: 0.7
```

### Setup Verification

```bash
# Test Python SDK
python -c "from dashscope import Generation; print('OK')"

# Test with Agent Pump
uv run agent-pump --backend qwen ask "Hello"
```

### Models

- `qwen-turbo` - Recommended for coding
- `qwen-plus` - For complex tasks
- `qwen-max` - Long context window

See [Qwen Documentation](https://help.aliyun.com/zh/dashscope/) for details.

## Claude Code

⚠️ **Beta Status**: Claude Code integration is experimental and may have issues.

### Prerequisites

```bash
# Install Anthropic CLI
pip install anthropic
```

### Configuration

**Option 1: Environment Variables**
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

**Option 2: Configuration File**
```yaml
backends:
  claude:
    model: claude-3-5-sonnet-20241022
    temperature: 0.7
```

### Setup Verification

```bash
# Test Anthropic CLI
anthropic --help

# Test with Agent Pump
uv run agent-pump --backend claude ask "Hello"
```

### Models

- `claude-3-5-sonnet-20241022` - Current Sonnet 3.5
- `claude-3-5-opus-20240229` - Higher quality, slower
- `claude-3-haiku-20240307` - Fast, for simple tasks

See [Anthropic Models](https://docs.anthropic.com/en/docs/about-models) for details.

### Known Issues

- File operations may not work reliably
- Some tools may not be available
- Use as secondary backend with Gemini as fallback

## OpenCode

⚠️ **Beta Status**: OpenCode integration is experimental and may have issues.

### Prerequisites

```bash
# Install OpenCode CLI
npm install -g @opencode/cli
```

### Configuration

**Option 1: Environment Variables**
```bash
export OPENCODE_API_KEY="your-api-key-here"
```

**Option 2: Configuration File**
```yaml
backends:
  opencode:
    model: gpt-4
    temperature: 0.7
```

### Setup Verification

```bash
# Test OpenCode CLI
opencode --help

# Test with Agent Pump
uv run agent-pump --backend opencode ask "Hello"
```

### Configuration File

Create `~/.config/opencode/config.yaml`:
```yaml
backend: gpt-4
temperature: 0.7
max_tokens: 4000
```

### Known Issues

- Experimental integration
- May require manual setup
- Not recommended as primary backend

## Pi Coding Agent

Pi is a minimalist, open-source terminal coding agent harness that supports multiple LLM providers (15+) and is highly customizable.

### Prerequisites

Install the Pi Coding Agent globally using npm:

```bash
npm install -g @earendil-works/pi-coding-agent
```

### Configuration

**Option 1: Environment Variables**
Pi is provider-agnostic. Provide your API keys based on the backend you configure:
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
export GOOGLE_API_KEY="your-api-key-here"
```

**Option 2: Configuration File**
Set as your default backend or specify provider and model overrides in `.agent-pump/config.yml`:
```yaml
backends:
  default: pi
  pi:
    extra_args:
      - "--provider"
      - "anthropic"
      - "--model"
      - "claude-3-5-sonnet"
```

### Setup Verification

```bash
# Verify pi CLI works
pi --help

# Test with Agent Pump
uv run agent-pump --backend pi ask "Hello" ./your-project
```

## Dry Run

Dry Run mode doesn't make actual API calls - it simulates responses for testing.

### Configuration

**Use via CLI:**
```bash
uv run agent-pump ./your-project --dry-run
```

**Or in TUI:**
Press `d` to toggle dry-run mode.

### What to Expect

- Fast execution (no network calls)
- Simulated responses
- No actual code changes
- Useful for testing workflows

## Fallback Chains

Configure multiple backends with automatic fallback if primary fails.

### Configuration Example

```yaml
backends:
  default: gemini
  fallback_chain:
    - qwen
    - claude
    - opencode
```

### Behavior

1. **Primary Backend** (gemini) tried first
2. **Fallback 1** (qwen) tried if gemini fails
3. **Fallback 2** (claude) tried if both fail
4. **Fallback 3** (opencode) tried if all others fail

### Use Cases

- **Reliability**: Use multiple providers to avoid downtime
- **Cost Optimization**: Mix providers to spread spending
- **Feature Testing**: Test different models for your use case

### Configuration File

Add to `~/.config/agent-pump/config.yml`:
```yaml
backends:
  default: gemini
  gemini:
    model: gemini-2.5-pro
    temperature: 0.7
    max_retries: 3
  qwen:
    model: qwen-turbo
    temperature: 0.7
    max_retries: 3
  fallback_chain:
    - qwen
    - claude
```

## Troubleshooting

### Common Issues

#### "Backend not available"

**Problem**: Agent Pump reports backend as unavailable.

**Solution**:
```bash
# Check backend is installed
which gemini-cli

# Check API key is set
echo $GEMINI_API_KEY

# Test backend directly
gemini-cli "test"
```

#### "API key invalid"

**Problem**: Authentication fails with invalid key error.

**Solution**:
1. Verify API key is correct
2. Check key has required permissions
3. Ensure key is active (not revoked)
4. Try regenerating the key

#### "Rate limit exceeded"

**Problem**: Backend rejects requests due to rate limits.

**Solution**:
1. Check your API quota
2. Increase budget limits in config
3. Use fallback chain to spread requests
4. Implement retry with exponential backoff

#### "Model not found"

**Problem**: Specified model name is invalid.

**Solution**:
1. Check model name spelling
2. Verify model is available in your region
3. Check model availability for your API tier

### Debug Mode

Enable debug logging to troubleshoot backend issues:

```bash
# Set environment variable
export AGENT_PUMP_DEBUG=1

# Run Agent Pump
uv run agent-pump ./your-project
```

### Testing Backends

Test each backend independently before using in Agent Pump:

```bash
# Gemini
gemini-cli "Write a Python function that adds two numbers"

# Qwen (using Python)
python -c "from dashscope import Generation; print(Generation.call(...))"

# Claude
anthropic message "Write a Python function"

# OpenCode
opencode ask "Write a Python function"
```

## Performance Tips

1. **Use Appropriate Models**
   - Simple queries: Use faster models (flash, haiku, turbo)
   - Complex tasks: Use larger models (pro, plus, max)

2. **Context Management**
   - Clear conversation history for new tasks
   - Use focused prompts
   - Limit file context to relevant files

3. **Temperature Settings**
   - Lower (0.2-0.5): More deterministic, better for code
   - Higher (0.7-1.0): More creative, better for brainstorming

4. **Batch Operations**
   - Let Agent Pump run the full workflow
   - Avoid manual interruption unless necessary
   - Use checkpoints to save progress

## Cost Management

Track and manage API costs with built-in cost tracking:

```bash
# Show costs for current project
uv run agent-pump cost show ./your-project

# Show budget status
uv run agent-pump budget show

# Enable budget limits
uv run agent-pump budget enable

# Configure limits
uv run agent-pump budget config --weekly 50 --monthly 200
```

See [features.md](features.md#cost-tracking) for detailed cost tracking documentation.

## Next Steps

- [ ] Configure your preferred backend
- [ ] Set up API keys
- [ ] Test backend independently
- [ ] Create test project with ROADMAP.md
- [ ] Run first workflow in dry-run mode
- [ ] Enable production workflow
