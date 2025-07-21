# AI Agent Payments SDK - Integration Examples

This directory contains integration examples showing how to use the AI Agent Payments SDK with popular AI agent frameworks and platforms.

## 🚀 Framework Integrations

### LangGraph Integration
**Location:** `examples/langgraph/`

Complex LangGraph workflow examples with payment integration.

**Features:**
- Multi-step payment integration
- State management with payments
- Complex workflow orchestration
- Agent-driven payment processing

**Files:**
- `movie_ticket_booking.py` - Complex workflow example with payment controls

**Quick Start:**
```bash
python examples/langgraph/movie_ticket_booking.py
```

## 🔗 Other Integrations

### CrewAI Integration
**File:** `crewai_monetized_example.py`

Integrating payments with CrewAI agents and monetizing AI agent workflows.

**Features:**
- CrewAI framework integration
- Monetized agent workflows
- Payment-gated AI tasks
- Subscription and pay-per-use models
- **No API keys required** - uses mock provider

### PetNameGenius Story
**File:** `petnamegenius_story.py`

Real-world SaaS application story with AI Pet Name Generator and monetization.

**Features:**
- Real-world SaaS application story
- AI Pet Name Generator with monetization
- Freemium to premium upgrade flow
- Usage limit enforcement
- **No API keys required** - uses mock provider

## 🛠️ Setup and Configuration

### Dependencies

Each integration may have specific dependencies:

```bash
# LangGraph
pip install langgraph

# CrewAI (may have conflicts)
pip install crewai
```

### Environment Variables

```bash
# Payment Provider Keys (optional for demo)
export STRIPE_SECRET_KEY="sk_test_..."
export PAYPAL_CLIENT_ID="your_paypal_client_id"
export PAYPAL_CLIENT_SECRET="your_paypal_client_secret"
export INFURA_PROJECT_ID="your_infura_project_id"
export WALLET_ADDRESS="0xYourWalletAddress"
```

## 🎯 Usage Examples

### LangGraph
```python
# Run the movie ticket booking example
python examples/langgraph/movie_ticket_booking.py
```

### CrewAI
```python
# Run the CrewAI monetized example
python examples/integrations/crewai_monetized_example.py
```

### PetNameGenius
```python
# Run the PetNameGenius story
python examples/integrations/petnamegenius_story.py
```

## 📚 Documentation

- [AI Agent Payments SDK Documentation](../README.md) - Main SDK documentation
- [Payment Provider Guides](../../docs/) - Payment provider specific guides
- [Examples Overview](../README.md) - Complete examples documentation

## 🤝 Contributing

To add new integrations:

1. Create a new directory for your integration (if it's a major framework)
2. Include example code and documentation
3. Add requirements file if needed
4. Update this README with integration details
5. Ensure examples work without external API keys or dependencies

## 🔗 Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [CrewAI Documentation](https://docs.crewai.com/)
- [AI Agent Payments SDK Documentation](../README.md) 