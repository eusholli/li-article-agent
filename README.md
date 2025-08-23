# LinkedIn Article Generator - Usage Guide

A DSPy-powered REACT system that transforms article drafts or outlines into world-class LinkedIn articles through intelligent web search, context integration, and iterative improvement with comprehensive scoring.

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

The LinkedIn Article Generator uses a sophisticated REACT (Reason-Act-Observe) process with intelligent web search:

1. **Draft Analysis**: Analyzes your input to determine if web research would be beneficial
2. **Intelligent Web Search**: Uses Tavily API to gather relevant, current context when needed
3. **Enhanced Generation**: Creates articles with rich context and supporting evidence
4. **Comprehensive Scoring**: Evaluates using 18 criteria categories (180 total points)
5. **Gap Analysis**: Identifies specific improvement areas
6. **Iterative Refinement**: Generates improved versions until target achieved
7. **World-Class Output**: Delivers articles scoring ≥89% (world-class tier)

### Key Features
- **REACT Architecture**: Intelligent reasoning about when to search for additional context
- **Web Research Integration**: Automatic gathering of relevant, up-to-date information
- **Draft Scoping**: Comprehensive analysis of input drafts before generation
- **Citation-Worthy Content**: Filters web content for high-quality, authoritative sources
- **HTML Content Processing**: Robust cleaning and processing of web-scraped content
- **Multi-Provider LLM Support**: OpenRouter, OpenAI, Anthropic, Ollama integration

## Scoring System

The system uses a comprehensive 180-point scoring system with these categories:

### Core Thinking (High Weight - 120 points)
- **First-Order Thinking** (45 points): Clear, logical reasoning and breaking down to fundamentals
- **Strategic Deconstruction & Synthesis** (75 points): Deep system analysis and insight synthesis

### Content Quality & Engagement (60 points)
- **Hook & Engagement** (10 points): Attention-grabbing opening and reader connection
- **Storytelling & Structure** (10 points): Compelling narrative and clear organization
- **Authority & Credibility** (10 points): Expertise demonstration and trustworthiness
- **Idea Density & Clarity** (10 points): Rich content with clear communication
- **Reader Value & Actionability** (10 points): Practical takeaways and useful insights
- **Call to Connection** (10 points): Community building and discussion prompts

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

**Note**: The system automatically determines whether web research would benefit your article and searches for relevant context when needed.

### Advanced Options

```bash
# Customize generation parameters
python main.py \
  --target-score 85 \
  --max-iterations 8 \
  --word-count-min 1800 \
  --word-count-max 2200

# Use different LLM models for specific components
python main.py --generator-model "openrouter/anthropic/claude-3-sonnet" \
               --judge-model "openrouter/openai/gpt-4o" \
               --rag-model "openrouter/moonshotai/kimi-k2:free"

# Save output and export results
python main.py \
  --output generated_article.md \
  --export-results generation_results.json

# Quiet mode (minimal output)
python main.py --quiet --file draft.txt --output article.md
```

### Full Options Reference

```
--draft, -d              Article draft or outline text (enclose in quotes)
--file, -f               Path to file containing the draft or outline
--target-score, -t       Target score percentage (default: 89.0)
--max-iterations, -i     Maximum improvement iterations (default: 10)
--word-count-min         Minimum target word count (default: 2000)
--word-count-max         Maximum target word count (default: 2500)
--generator-model        LLM model for article generation (default: openrouter/moonshotai/kimi-k2:free)
--judge-model            LLM model for article scoring (default: openrouter/deepseek/deepseek-r1-0528:free)
--rag-model              LLM model for web search/retrieval (default: openrouter/deepseek/deepseek-r1-0528:free)
--output, -o             Output file path for generated article
--export-results         Export detailed results to JSON file
--quiet, -q              Suppress progress messages
```

**REACT Features**: The system automatically analyzes your draft and determines whether web research would enhance the article. When beneficial, it searches for relevant context using the Tavily API and integrates findings into the generation process.

## Configuration

### Required API Keys

The system requires API keys for both LLM providers and web search:

#### LLM Provider Setup
The system supports multiple LLM providers through DSPy:

**OpenRouter (Recommended)**
```bash
export OPENROUTER_API_KEY="your-api-key"
python main.py --generator-model "openrouter/anthropic/claude-3-sonnet"
```

**OpenAI**
```bash
export OPENAI_API_KEY="your-api-key"
python main.py --generator-model "gpt-4"
```

**Anthropic**
```bash
export ANTHROPIC_API_KEY="your-api-key"
python main.py --generator-model "claude-3-sonnet-20240229"
```

**Local Models (Ollama)**
```bash
# Start Ollama server first
ollama serve

# Use local model
python main.py --generator-model "ollama/llama2"
```

#### Web Search Setup (Required)
For the REACT system's web research capabilities:

```bash
export TAVILY_API_KEY="your-tavily-api-key"
```

Get your free Tavily API key at: https://tavily.com/

### Model Recommendations

#### For Article Generation (--generator-model)
- **Best Quality**: `openrouter/anthropic/claude-3-sonnet`
- **Good Balance**: `openrouter/openai/gpt-4-turbo`
- **Cost-Effective**: `openrouter/moonshotai/kimi-k2:free` (default)
- **Local/Private**: `ollama/llama2` or `ollama/mistral`

#### For Article Scoring (--judge-model)
- **Best Quality**: `openrouter/openai/gpt-4o`
- **Good Balance**: `openrouter/deepseek/deepseek-r1-0528:free` (default)
- **Cost-Effective**: `openrouter/moonshotai/kimi-k2:free`

#### For Web Search/RAG (--rag-model)
- **Best Quality**: `openrouter/anthropic/claude-3-sonnet`
- **Good Balance**: `openrouter/deepseek/deepseek-r1-0528:free` (default)
- **Cost-Effective**: `openrouter/moonshotai/kimi-k2:free`

#### Mixed Model Usage Examples
```bash
# High-quality generation with cost-effective scoring
python main.py --generator-model "openrouter/anthropic/claude-3-sonnet" \
               --judge-model "openrouter/deepseek/deepseek-r1-0528:free"

# All premium models for best results
python main.py --generator-model "openrouter/anthropic/claude-3-sonnet" \
               --judge-model "openrouter/openai/gpt-4o" \
               --rag-model "openrouter/anthropic/claude-3-sonnet"

# All free models for cost-effective operation
python main.py --generator-model "openrouter/moonshotai/kimi-k2:free" \
               --judge-model "openrouter/deepseek/deepseek-r1-0528:free" \
               --rag-model "openrouter/deepseek/deepseek-r1-0528:free"
```

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
🤖 Setting up DSPy with model: openrouter/moonshotai/kimi-k2:free
🔧 Model Configuration:
   Generator: openrouter/moonshotai/kimi-k2:free
   Judge: openrouter/deepseek/deepseek-r1-0528:free
   RAG: openrouter/deepseek/deepseek-r1-0528:free
📝 Using provided draft (247 characters)
🎯 Target score: ≥89.0%
🔄 Max iterations: 10
📏 Word count range: 2000-2500

🚀 Starting LinkedIn Article REACT Generation Process
============================================================

🧠 REACT Phase: Reasoning about topic and research needs
📊 Topic: "The Future of Remote Work"
🔍 Research Decision: YES - Current trends and data would enhance this article
📝 Search Queries: ["remote work statistics 2024", "hybrid work trends", "remote work productivity studies"]

🌐 REACT Phase: Searching for relevant context
🔍 Searching: remote work statistics 2024
🔍 Searching: hybrid work trends  
🔍 Searching: remote work productivity studies
✅ Found 8 relevant passages (total: 12,847 characters)
📊 Context enhanced with current data and trends

📝 REACT Phase: Generating article with enhanced context
✅ Initial article generated: 2,247 words

🔄 Iteration 1: Scoring and Analysis
----------------------------------------
📊 Current Score: 142/180 (78.9%)
🎯 Target Score: ≥89%
🔍 Focus Areas: First-order thinking, Strategic deconstruction
✏️  Generating improved version...
📝 Version 2 created: 2,356 words

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
📝 Final Word Count: 2,356 words
📈 Score Improvement: +10.5%
📏 Word Count Change: +109 words

============================================================
🧠 REACT METADATA
============================================================
🔍 Web Research: YES (Enhanced with current data)
📊 Search Queries: 3 queries executed
🌐 Context Sources: 8 relevant passages found
📈 Context Benefit: Significant improvement in authority and evidence
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
  "react_metadata": {
    "topic_analysis": "The Future of Remote Work",
    "research_decision": true,
    "search_queries": ["remote work statistics 2024", "hybrid work trends", "remote work productivity studies"],
    "context_found": true,
    "passages_count": 8,
    "total_context_chars": 12847,
    "context_benefit": "Significant improvement in authority and evidence"
  },
  "generation_log": [
    "REACT: Analyzed topic and decided to search for context",
    "REACT: Found 8 relevant passages (12,847 chars)",
    "Version 1: Generated initial article with enhanced context (2,247 words)",
    "Version 2: Improved article (2,356 words, targeting First-order thinking, Strategic deconstruction)",
    "Iteration 2: Target achieved (89.4%)"
  ],
  "version_history": [
    {
      "version": 1,
      "word_count": 2247,
      "score": 142,
      "percentage": 78.9,
      "category_scores": {...}
    },
    {
      "version": 2,
      "word_count": 2356,
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
python main.py --generator-model "openrouter/openai/gpt-3.5-turbo"

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
- Use faster models: `--generator-model "openrouter/openai/gpt-3.5-turbo"`
- Reduce max iterations: `--max-iterations 5`
- Lower target score: `--target-score 85`

#### High API Costs
- Use free models: `--generator-model "openrouter/moonshotai/kimi-k2:free" --judge-model "openrouter/deepseek/deepseek-r1-0528:free"`
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

# Setup (requires both LLM and Tavily API keys)
setup_dspy_provider("openrouter/anthropic/claude-3-sonnet")
generator = LinkedInArticleGenerator(
    target_score_percentage=89.0,
    generator_model="openrouter/anthropic/claude-3-sonnet",
    judge_model="openrouter/openai/gpt-4o",
    rag_model="openrouter/deepseek/deepseek-r1-0528:free"
)

# Generate article with REACT system
draft = "Your article outline here..."
result = generator.generate_article(draft, verbose=True)

# Access results
final_article = result["final_article"]
final_score = result["final_score"]
target_achieved = result["target_achieved"]
react_metadata = result["react_metadata"]

# Export results with REACT metadata
generator.export_results("results.json")
```

### Batch Processing

```python
import os
from pathlib import Path
from linkedin_article_generator import LinkedInArticleGenerator

# Initialize generator with specific models
generator = LinkedInArticleGenerator(
    target_score_percentage=89.0,
    generator_model="openrouter/anthropic/claude-3-sonnet",
    judge_model="openrouter/openai/gpt-4o",
    rag_model="openrouter/deepseek/deepseek-r1-0528:free"
)

# Process multiple drafts
draft_files = Path("drafts/").glob("*.txt")
for draft_file in draft_files:
    with open(draft_file) as f:
        draft_content = f.read()
    
    result = generator.generate_article(draft_content, verbose=False)
    
    # Save result with REACT metadata
    output_file = f"generated/{draft_file.stem}_article.md"
    with open(output_file, "w") as f:
        f.write(result["final_article"])
    
    # Export detailed results including web research data
    results_file = f"generated/{draft_file.stem}_results.json"
    generator.export_results(results_file)
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
