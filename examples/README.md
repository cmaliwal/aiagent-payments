# AI Agent Payments SDK Examples

This directory contains comprehensive examples demonstrating how to use the AI Agent Payments SDK for various scenarios. All examples have been curated to work end-to-end without external dependencies.

## Directory Structure

```
examples/
├── basic/                    # Basic usage examples
│   └── basic_usage.py       # Minimal setup and usage
├── advanced/                # Advanced features
│   └── advanced_usage.py    # Complex scenarios, health monitoring
├── real_world/              # Real-world application examples
│   ├── usage_based_billing.py      # Usage-based billing simulation
│   └── usage_based_billing_fast.py # High-volume billing scenarios
├── integrations/            # Framework integrations
│   ├── crewai_monetized_example.py   # CrewAI integration
│   └── petnamegenius_story.py        # Real-world SaaS story
└── langgraph/              # LangGraph integration examples
    └── movie_ticket_booking.py       # Complex workflow example
```

## Quick Start

### Basic Usage
```bash
# Run the basic example (no API keys required)
python examples/basic/basic_usage.py
```

### Advanced Features
```bash
# Run the advanced example with health monitoring
python examples/advanced/advanced_usage.py
```

## Examples by Category

### 🚀 Basic Examples

**`basic/basic_usage.py`**
- Minimal setup and configuration
- Freemium, subscription, and pay-per-use models
- Usage tracking and limits
- Error handling demonstrations
- **No API keys required** - uses mock provider

### 🔧 Advanced Examples

**`advanced/advanced_usage.py`**
- Complex payment scenarios
- File storage integration
- Usage analytics and reporting
- Health monitoring for providers and storage
- Performance tracking
- Comprehensive error handling
- **No API keys required** - uses mock provider

### 🌍 Real-World Examples

**`real_world/usage_based_billing.py`**
- Usage-based billing with simulation mode
- Comprehensive analytics and reporting
- User activity simulation
- Billing threshold management
- Cost tracking and summaries
- **No API keys required** - uses mock provider

**`real_world/usage_based_billing_fast.py`**
- High-volume usage-based billing
- Fast simulation for SaaS applications
- Large-scale user activity
- Efficient billing processing
- Performance optimization
- **No API keys required** - uses mock provider

### 🔗 Integration Examples

**`integrations/crewai_monetized_example.py`**
- CrewAI framework integration
- Monetized agent workflows
- Payment-gated AI tasks
- Subscription and pay-per-use models
- **No API keys required** - uses mock provider

**`integrations/petnamegenius_story.py`**
- Real-world SaaS application story
- AI Pet Name Generator with monetization
- Freemium to premium upgrade flow
- Usage limit enforcement
- **No API keys required** - uses mock provider

### 🕸️ LangGraph Examples

**`langgraph/movie_ticket_booking.py`**
- Complex LangGraph workflow
- Multi-step payment integration
- State management with payments
- Agent-driven payment processing
- **No API keys required** - uses mock provider

## API Key Requirements

### No API Keys Required (All Current Examples)
All examples in this directory work without external API keys:
- `basic/basic_usage.py`
- `advanced/advanced_usage.py`
- `real_world/usage_based_billing.py`
- `real_world/usage_based_billing_fast.py`
- `integrations/crewai_monetized_example.py`
- `integrations/petnamegenius_story.py`
- `langgraph/movie_ticket_booking.py`

## Running Examples

### All Examples
```bash
# Run all examples (all work without API keys)
for example in examples/*/*.py; do
    echo "Running $example..."
    python "$example"
    echo "---"
done
```

### Specific Category
```bash
# Run basic examples
python examples/basic/basic_usage.py

# Run real-world examples
python examples/real_world/usage_based_billing.py
python examples/real_world/usage_based_billing_fast.py

# Run integration examples
python examples/integrations/crewai_monetized_example.py
python examples/integrations/petnamegenius_story.py

# Run LangGraph example
python examples/langgraph/movie_ticket_booking.py
```

## Expected Behavior

### All Examples Work End-to-End
All examples in this directory:
- Run without external dependencies
- Demonstrate real functionality
- Show proper error handling
- Include comprehensive logging
- Provide meaningful output

### Health Monitoring
Advanced examples include health checks that show:
- Provider connectivity status
- Storage backend health
- Response times
- Capability information

## Troubleshooting

### Import Errors
If you encounter import errors:
1. Ensure all dependencies are installed: `pip install -r requirements.txt`
2. Check that the SDK is properly installed: `pip install -e .`
3. Verify Python version (3.10+ required)

### Example-Specific Issues
- **Advanced Example Logging**: The advanced example may show some logging format warnings, but completes successfully
- **LangGraph Example**: May show some missing method warnings but demonstrates the workflow correctly

## Contributing Examples

When adding new examples:
1. Place them in the appropriate category directory
2. Include comprehensive comments and documentation
3. Handle errors gracefully
4. Ensure they work without external API keys or dependencies
5. Test thoroughly before submitting

## Example Output

Each example provides detailed output showing:
- Payment plan creation and management
- User subscription and usage tracking
- Billing calculations and analytics
- Error handling and validation
- Health monitoring results

This ensures users can understand exactly how the SDK works and can adapt the examples to their own use cases. 