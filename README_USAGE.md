# LinkedIn Article Generator - Usage Guide

A DSPy-powered system that transforms article drafts or outlines into world-class LinkedIn articles through iterative improvement and comprehensive scoring.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up your LLM provider (see Configuration section)
export OPENROUTER_API_KEY="your-api-key-here"

# Generate an article from a draft
python main.py --draft "Your article outline here..."

# Generate from a file
python main.py --file my_draft.txt

# Customize target score and iterations
python main.py --target-score 85 --max-iterations 5
```

## System Overview

The LinkedIn Article Generator uses a sophisticated iterative improvement process:

1. **Initial Generation**: Creates an article from your draft/outline
2. **Comprehensive Scoring**: Evaluates using 18 criteria categories (180 total points)
3. **Gap Analysis**: Identifies specific improvement areas
4. **Iterative Refinement**: Generates improved versions until target achieved
5. **World-Class Output**: Delivers articles scoring ≥89% (world-class tier)

## Scoring System

The system uses a comprehensive 180-point scoring system with these categories:

### Core Thinking (High Weight)
- **First-Order Thinking** (15 points): Clear, logical reasoning
- **Strategic Deconstruction** (15 points): Breaking down complex topics
- **Insight Quality** (15 points): Novel, valuable perspectives
- **Practical Application** (10 points): Actionable takeaways

### Content Quality (Medium Weight)
- **Narrative Structure** (10 points): Compelling storytelling
- **Evidence & Examples** (10 points): Supporting data and cases
- **Clarity & Precision** (10 points): Clear communication
- **Professional Tone** (10 points): Appropriate voice

### Engagement (Medium Weight)
- **Hook Effectiveness** (10 points): Attention-grabbing opening
- **Emotional Resonance** (10 points): Connecting with readers
- **Call to Action** (10 points): Clear next steps
- **Discussion Prompts** (10 points): Encouraging interaction

### Technical Excellence (Lower Weight)
- **LinkedIn Optimization** (8 points): Platform-specific features
- **Formatting & Structure** (8 points): Visual organization
- **Length Optimization** (7 points): Ideal word count (2000-2500)
- **SEO Considerations** (7 points): Discoverability
- **Accessibility** (5 points): Inclusive design
- **Compliance** (5 points): Platform guidelines

### Performance Tiers
- **89%+**: World-class — publish as is
- **72%+**: Strong, but tighten weak areas  
- **56%+**: Needs restructuring and sharper insights
- **<56%**: Rework before publishing

## Command Line Interface

### Basic Usage

```bash
# Use default sample (for testing)
python main.py

# Provide draft text directly
python main.py --draft "AI is transforming business operations..."

# Load draft from file
python main.py --file articles/my_draft.txt
```

### Advanced Options

```bash
# Customize generation parameters
python main.py \
  --target-score 85 \
  --max-iterations 8 \
  --word-count-min 1800 \
  --word-count-max 2200

# Use different LLM model
python main.py --model "openrouter/anthropic/claude-3-haiku"

# Save output and export results
python main.py \
  --output generated_article.md \
  --export-results generation_results.json

# Quiet mode (minimal output)
python main.py --quiet --file draft.txt --output article.md
```

### Full Options Reference

```
--draft, -d          Article draft or outline text (enclose in quotes)
--file, -f           Path to file containing the draft or outline
--target-score, -t   Target score percentage (default: 89.0)
--max-iterations, -i Maximum improvement iterations (default: 10)
--word-count-min     Minimum target word count (default: 2000)
--word-count-max     Maximum target word count (default: 2500)
--model, -m          LLM model to use (default: openrouter/moonshotai/kimi-k2:free)
--output, -o         Output file path for generated article
--export-results     Export detailed results to JSON file
--quiet, -q          Suppress progress messages
```

## Configuration

### LLM Provider Setup

The system supports multiple LLM providers through DSPy. Configure your preferred provider:

#### OpenRouter (Recommended)
```bash
export OPENROUTER_API_KEY="your-api-key"
python main.py --model "openrouter/anthropic/claude-3-sonnet"
```

#### OpenAI
```bash
export OPENAI_API_KEY="your-api-key"
python main.py --model "gpt-4"
```

#### Anthropic
```bash
export ANTHROPIC_API_KEY="your-api-key"
python main.py --model "claude-3-sonnet-20240229"
```

#### Local Models (Ollama)
```bash
# Start Ollama server first
ollama serve

# Use local model
python main.py --model "ollama/llama2"
```

### Model Recommendations

- **Best Quality**: `openrouter/anthropic/claude-3-sonnet`
- **Good Balance**: `openrouter/openai/gpt-4-turbo`
- **Cost-Effective**: `openrouter/moonshotai/kimi-k2:free`
- **Local/Private**: `ollama/llama2` or `ollama/mistral`

## Input Formats

### Draft Text Examples

#### Simple Outline
```
# The Future of Remote Work

Key benefits:
- Flexibility for employees
- Access to global talent
- Reduced costs

Challenges:
- Communication barriers
- Company culture
- Team management

The future is hybrid.
```

#### Detailed Draft
```
Remote work has fundamentally changed business operations. 

Companies are discovering that distributed teams can be more productive than traditional office setups. The key is implementing the right tools and processes.

Three critical success factors:
1. Clear communication protocols
2. Results-oriented performance metrics  
3. Intentional culture building

However, challenges remain around maintaining team cohesion and ensuring equal opportunities for remote vs. in-office employees.
```

#### Bullet Points
```
AI in Healthcare:
• Diagnostic accuracy improvements
• Personalized treatment plans
• Drug discovery acceleration
• Administrative automation
• Patient monitoring systems
• Ethical considerations needed
```

### File Input

Save your draft in any text file:

```bash
# Create draft file
echo "Your article content here..." > my_draft.txt

# Generate article
python main.py --file my_draft.txt
```

## Output Examples

### Console Output
```
🚀 Starting LinkedIn Article Generation Process
============================================================
📝 Generating initial article...
✅ Initial article generated: 1847 words

🔄 Iteration 1: Scoring and Analysis
----------------------------------------
📊 Current Score: 142/180 (78.9%)
🎯 Target Score: ≥89%
🔍 Focus Areas: First-order thinking, Strategic deconstruction, Insight quality
✏️  Generating improved version...
📝 Version 2 created: 2156 words

🔄 Iteration 2: Scoring and Analysis
----------------------------------------
📊 Current Score: 161/180 (89.4%)
🎯 Target Score: ≥89%
🎉 TARGET ACHIEVED! Article reached world-class status!

============================================================
🏆 FINAL RESULTS
============================================================
📊 Final Score: 161/180 (89.4%)
🎯 Target: ≥89%
✅ Target Achieved: YES
🔄 Iterations Used: 2/10
📝 Final Word Count: 2156 words
📈 Score Improvement: +10.5%
📏 Word Count Change: +309 words
```

### Generated Article Structure
```markdown
# [Compelling Title]

[Hook paragraph that grabs attention]

[Main content with clear structure, insights, and examples]

## Key Takeaways
- [Actionable insight 1]
- [Actionable insight 2]
- [Actionable insight 3]

[Call to action and discussion prompt]

---
What's your experience with [topic]? Share your thoughts in the comments.

#hashtag1 #hashtag2 #hashtag3
```

### JSON Export
```json
{
  "target_score_percentage": 89.0,
  "final_achieved": true,
  "generation_log": [
    "Version 1: Generated initial article (1847 words)",
    "Version 2: Improved article (2156 words, targeting First-order thinking, Strategic deconstruction, Insight quality)",
    "Iteration 2: Target achieved (89.4%)"
  ],
  "version_history": [
    {
      "version": 1,
      "word_count": 1847,
      "score": 142,
      "percentage": 78.9,
      "category_scores": {...}
    },
    {
      "version": 2,
      "word_count": 2156,
      "score": 161,
      "percentage": 89.4,
      "category_scores": {...}
    }
  ],
  "final_article": "...",
  "final_score_details": {...}
}
```

## Best Practices

### Input Preparation
1. **Provide Clear Structure**: Use headings, bullet points, or numbered lists
2. **Include Key Points**: Outline main arguments and supporting evidence
3. **Add Context**: Mention target audience and article purpose
4. **Specify Examples**: Include relevant case studies or data points

### Optimization Tips
1. **Start with Quality**: Better input drafts lead to better final articles
2. **Iterate Strategically**: Let the system identify and fix weak areas
3. **Monitor Progress**: Watch score improvements across iterations
4. **Balance Constraints**: Consider both score and word count targets

### Common Issues
1. **Low Initial Scores**: Normal for rough drafts; system will improve them
2. **Word Count Mismatches**: System balances length with quality automatically
3. **Slow Convergence**: Complex topics may need more iterations
4. **API Limits**: Use cost-effective models for testing, premium for production

## Troubleshooting

### Common Errors

#### API Key Issues
```bash
# Error: No API key found
export OPENROUTER_API_KEY="your-key-here"

# Verify key is set
echo $OPENROUTER_API_KEY
```

#### Model Not Found
```bash
# Use supported model
python main.py --model "openrouter/openai/gpt-3.5-turbo"

# Check available models in dspy_factory.py
```

#### File Not Found
```bash
# Check file path
ls -la my_draft.txt

# Use absolute path if needed
python main.py --file /full/path/to/draft.txt
```

### Performance Issues

#### Slow Generation
- Use faster models: `openrouter/openai/gpt-3.5-turbo`
- Reduce max iterations: `--max-iterations 5`
- Lower target score: `--target-score 85`

#### High API Costs
- Use free models: `openrouter/moonshotai/kimi-k2:free`
- Set lower iteration limits
- Use local models with Ollama

#### Quality Issues
- Improve input draft quality
- Use higher-quality models
- Increase iteration limits
- Adjust target scores

## Integration

### Python API Usage

```python
from linkedin_article_generator import LinkedInArticleGenerator
from dspy_factory import setup_dspy_provider

# Setup
setup_dspy_provider("openrouter/anthropic/claude-3-sonnet")
generator = LinkedInArticleGenerator(target_score_percentage=89.0)

# Generate article
draft = "Your article outline here..."
result = generator.generate_article(draft, verbose=True)

# Access results
final_article = result["final_article"]
final_score = result["final_score"]
target_achieved = result["target_achieved"]

# Export results
generator.export_results("results.json")
```

### Batch Processing

```python
import os
from pathlib import Path

# Process multiple drafts
draft_files = Path("drafts/").glob("*.txt")
for draft_file in draft_files:
    with open(draft_file) as f:
        draft_content = f.read()
    
    result = generator.generate_article(draft_content, verbose=False)
    
    # Save result
    output_file = f"generated/{draft_file.stem}_article.md"
    with open(output_file, "w") as f:
        f.write(result["final_article"])
```

## Support

### Getting Help
- Check this documentation first
- Review error messages carefully
- Verify API keys and model availability
- Test with simple examples

### Contributing
- Report issues with detailed error messages
- Suggest improvements to scoring criteria
- Share successful article examples
- Contribute model configurations

### Performance Monitoring
- Track generation success rates
- Monitor API usage and costs
- Measure article engagement metrics
- Optimize based on real-world performance

---

For technical details, see the implementation documentation in the `memory-bank/` directory.
