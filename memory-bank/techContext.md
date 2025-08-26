# Technical Context - LinkedIn Article Generator

## Technology Stack

### Core Framework
- **DSPy:** Stanford's framework for programming language models
  - Version: Latest (from stanfordnlp/dspy)
  - Purpose: Structured LLM interactions and optimization
  - Key Features: Signatures, Modules, ChainOfThought, optimization algorithms

### Dependencies
- **Python 3.8+:** Core runtime environment
- **dspy:** Main framework for LLM programming
- **pydantic:** Data validation and type safety
- **python-dotenv:** Environment variable management
- **tavily-python:** High-performance web search API client for RAG
- **tiktoken:** Accurate token counting for context window management
- **asyncio:** Built-in async support for concurrent operations
- **attachments:** File processing and text extraction

### LLM Provider Integration
- **OpenRouter API:** Primary LLM access point
- **Default Model:** openrouter/moonshotai/kimi-k2:free (fallback for all components)
- **Component-Specific Models:** Runtime selection via command-line arguments
- **Enhanced Configuration:** Via extended dspy_factory.py with model instance management
- **Model Caching:** Performance optimization through instance reuse
- **API Key:** Stored in .env file as OPENROUTER_API_KEY

## Existing Infrastructure

### Enhanced Factory System (dspy_factory.py)
- **Model Instance Management:** New functions for component-specific model creation
  - `get_model_instance(model_name)`: Creates and caches LM instances
  - `create_component_lm(model_name)`: Wraps models in ConfiguredLM for context management
  - `get_fallback_model()`: Provides intelligent fallback to default model
- **Performance Caching:** `_model_instance_cache` dictionary prevents redundant initialization
- **Backward Compatibility:** Existing `setup_dspy_provider()` unchanged for legacy usage
- **Error Handling:** Graceful fallbacks when model creation fails

### Scoring System (li_article_judge.py)
- **Architecture:** Comprehensive 180-point evaluation system
- **Categories:** 8 major scoring categories with weighted criteria
- **Data Models:** Pydantic-based ScoreResultModel and ArticleScoreModel
- **Integration:** Direct Python import for dynamic criteria access
- **Model Selection:** Optional model_name parameter for component-specific scoring
- **Word Count Integration:** ArticleScoreModel enhanced with optional word_count field for unified scoring

### Scoring Criteria Structure
```python
SCORING_CRITERIA = {
    "First-Order Thinking": [45 points total],
    "Strategic Deconstruction & Synthesis": [75 points total],
    "Hook & Engagement": [10 points total],
    "Storytelling & Structure": [10 points total],
    "Authority & Credibility": [10 points total],
    "Idea Density & Clarity": [10 points total],
    "Reader Value & Actionability": [10 points total],
    "Call to Connection": [10 points total]
}
```

### Performance Tiers
- **89%+:** World-class — publish as is
- **72%+:** Strong, but tighten weak areas
- **56%+:** Needs restructuring and sharper insights
- **<56%:** Rework before publishing

## Development Constraints

### Runtime Model Selection Requirements
- **Component Independence:** Each component can use different models
- **Backward Compatibility:** Existing --model argument must continue working
- **Fallback Logic:** Graceful degradation when specific models unavailable
- **Cost Optimization:** Support for mixing free and paid models
- **Performance:** Model instance caching for efficiency

### Word Count Requirements
- **Target Range:** 2000-2500 words
- **Rationale:** Optimal LinkedIn article length for engagement
- **Validation:** Automatic word counting and adjustment
- **Quality Balance:** Maintain quality while meeting length constraints

### Integration Requirements
- **Dynamic Criteria Loading:** Must adapt to changes in li_article_judge.py
- **No Modification:** Cannot modify existing li_article_judge.py code
- **Runtime Adaptation:** Detect and adapt to criteria changes automatically
- **Backward Compatibility:** Support existing scoring system interface
- **Model Flexibility:** Support any OpenRouter-compatible model

## DSPy Implementation Patterns

### Enhanced Signature Design
```python
class ArticleSignature(dspy.Signature):
    """Specific task description for LLM"""
    
    input_field = dspy.InputField(desc="Detailed input description")
    output_field = dspy.OutputField(desc="Expected output format")
```

### Enhanced Module Architecture with Model Selection
```python
class ArticleModule(dspy.Module):
    def __init__(self, model_name=None):
        super().__init__()
        if model_name:
            # Use component-specific model
            self.lm = create_component_lm(model_name)
            self.component = dspy.ChainOfThought(Signature, lm=self.lm)
        else:
            # Fall back to global DSPy configuration
            self.component = dspy.ChainOfThought(Signature)
    
    def forward(self, **inputs):
        return self.component(**inputs)
```

### Model Instance Management
```python
# Factory functions for model management
def get_model_instance(model_name: str) -> Any:
    """Get or create cached model instance"""
    
def create_component_lm(model_name: str) -> ConfiguredLM:
    """Create ConfiguredLM for component use"""
    
def get_fallback_model() -> str:
    """Get default fallback model name"""
```

### Error Handling Strategy
- **Retry Logic:** Multiple attempts for LLM calls
- **Fallback Mechanisms:** Graceful degradation on failures
- **Validation:** Output format and content validation
- **Logging:** Comprehensive error tracking and debugging

## Data Flow Architecture

### Input Processing
1. **Outline/Draft Input:** Text-based article outline or draft
2. **Criteria Extraction:** Dynamic loading from li_article_judge.py
3. **Context Preparation:** Combine input with current criteria

### Generation Pipeline
1. **Initial Generation:** Create first article draft
2. **Unified Scoring:** Combined quality and word count evaluation with ArticleScoreModel
3. **Target Achievement Check:** Single validation for both quality (≥89%) and length (2000-2500 words)
4. **Smart Feedback Analysis:** WordCountManager generates targeted improvement instructions based on scoring
5. **Iterative Refinement:** DSPy signatures include word length adjustment instructions for targeted improvements

### Output Validation
1. **Structure Check:** Ensure proper article format
2. **Unified Target Validation:** Combined quality (≥89%) and length (2000-2500 words) achievement check
3. **Integrated Scoring:** ArticleScoreModel includes word_count field for comprehensive evaluation
4. **Final Review:** Complete article ready for publication

## Performance Considerations

### Enhanced Optimization Strategies
- **Model Instance Caching:** `_model_instance_cache` prevents redundant model creation
- **Component LM Reuse:** ConfiguredLM instances cached for performance
- **Criteria Caching:** Avoid repeated criteria parsing
- **Incremental Improvement:** Targeted changes vs. complete rewrites
- **Early Termination:** Stop when targets achieved
- **Cost-Aware Processing:** Balance quality with API usage costs

### Enhanced Resource Management
- **API Rate Limits:** Respect OpenRouter usage limits across multiple models
- **Memory Usage:** Efficient handling of large articles and model instances
- **Processing Time:** Balance quality with generation speed per model
- **Cost Optimization:** Strategic model selection and minimal unnecessary LLM calls
- **Model Instance Lifecycle:** Proper cleanup and reuse of cached instances
- **Budget Management:** Track and optimize costs across different model tiers

## Development Environment

### Enhanced File Structure
```
/
├── memory-bank/           # Project documentation and context
├── li_article_judge.py    # Existing scoring system (enhanced with model selection)
├── linkedin_article_generator.py  # Article generation (enhanced with model selection)
├── rag.py                 # Original RAG retrieval (legacy)
├── rag_fast.py            # NEW: High-performance async RAG with intelligent packing
├── context_window_manager.py  # Centralized context window management
├── dspy_factory.py        # Enhanced LLM provider setup with model management
├── main.py                # Enhanced CLI with component-specific model arguments
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (API keys + TAVILY_API_KEY)
├── articles/              # Sample articles for testing
└── [other implementation files]
```

### Command-Line Interface
```bash
# Component-specific model selection
python main.py \
  --generator-model "openrouter/anthropic/claude-3-sonnet" \
  --judge-model "openrouter/openai/gpt-4o" \
  --rag-model "openrouter/moonshotai/kimi-k2:free" \
  --outline "Your article outline here"

# Backward compatible usage
python main.py \
  --model "openrouter/anthropic/claude-3-haiku" \
  --outline "Your article outline here"

# Mixed usage - specify some, let others default
python main.py \
  --model "openrouter/moonshotai/kimi-k2:free" \
  --judge-model "openrouter/openai/gpt-4o" \
  --outline "Your article outline here"
```

### New Command-Line Arguments
- `--generator-model`: Model for article generation and improvement operations
- `--judge-model`: Model for article scoring and evaluation operations  
- `--rag-model`: Model for web search and context retrieval operations
- `--model`: Universal fallback model (backward compatible)

### Enhanced Configuration Management
- **Environment Variables:** API keys and configuration (OPENROUTER_API_KEY + TAVILY_API_KEY)
- **Model Selection:** Component-specific model configuration via CLI
- **Default Settings:** Sensible defaults for all parameters (free models)
- **Cost Optimization:** Strategic model selection for budget management
- **User Customization:** Configurable targets and preferences
- **Debug Mode:** Enhanced logging with model usage tracking
- **Fallback Logic:** Intelligent degradation when models unavailable
- **RAG Configuration:** Tavily search depth, result limits, and processing parameters
- **Context Window Budgets:** Centralized allocation strategy (35% for RAG context)

## Quality Assurance

### Enhanced Testing Strategy
- **Unit Tests:** Individual component validation with model selection
- **Integration Tests:** End-to-end article generation with different model combinations
- **Model Selection Tests:** Verify component-specific model assignment
- **Scoring Tests:** Verify scoring system integration with different models
- **Performance Tests:** Measure generation speed and quality across model types
- **Cost Analysis Tests:** Validate cost optimization strategies
- **Fallback Tests:** Ensure graceful degradation when models unavailable

### Enhanced Validation Framework
- **Input Validation:** Ensure valid outlines and drafts
- **Model Configuration Validation:** Verify model names and availability
- **Output Validation:** Verify article quality and format
- **Criteria Compliance:** Check adherence to scoring requirements
- **Word Count Compliance:** Validate length constraints
- **Model Performance Validation:** Ensure models perform as expected
- **Cost Validation:** Verify cost optimization is working correctly

## Security Considerations

### API Key Management
- **Environment Variables:** Secure storage in .env file
- **Access Control:** Limit API key exposure
- **Error Handling:** Avoid key leakage in error messages
- **Rotation Support:** Easy API key updates

### Data Privacy
- **Local Processing:** Article content stays local
- **API Calls:** Only necessary data sent to LLM providers
- **Logging:** Avoid sensitive data in logs
- **Cleanup:** Temporary data removal after processing

## Enhanced Monitoring and Debugging

### Enhanced Logging Strategy
- **Progress Tracking:** Iteration-by-iteration progress with model attribution
- **Model Usage Tracking:** Log which models used for each operation
- **Error Logging:** Comprehensive error capture with model context
- **Performance Metrics:** Generation time and quality trends per model
- **Cost Tracking:** Monitor API usage and costs per model
- **Debug Output:** Detailed intermediate results with model information
- **Fallback Logging:** Track when and why fallbacks are used
- **RAG Performance Tracking:** Async operation timing, search result quality, and packing efficiency
- **Topic Analysis Logging:** Track topic extraction accuracy and search query effectiveness
- **Context Window Usage:** Monitor allocation efficiency and budget utilization

### Enhanced Metrics Collection
- **Success Rate:** Percentage of articles achieving targets per model combination
- **Iteration Count:** Average iterations to reach goals with different models
- **Quality Trends:** Score improvements over time by model type
- **Performance Benchmarks:** Speed and efficiency metrics per model
- **Cost Metrics:** API usage and cost analysis across model combinations
- **Model Effectiveness:** Track which models perform best for each operation type
- **Optimization Impact:** Measure benefits of strategic model selection
- **RAG Effectiveness:** Measure impact of web context on article quality and scoring
- **Search Query Quality:** Track relevance and usefulness of generated search queries
- **Content Packing Efficiency:** Monitor how well content fits within context budgets

### Enhanced Metrics Collection
- **Success Rate:** Percentage of articles achieving targets per model combination
- **Iteration Count:** Average iterations to reach goals with different models
- **Quality Trends:** Score improvements over time by model type
- **Performance Benchmarks:** Speed and efficiency metrics per model
- **Cost Metrics:** API usage and cost analysis across model combinations
- **Model Effectiveness:** Track which models perform best for each operation type
- **Optimization Impact:** Measure benefits of strategic model selection
