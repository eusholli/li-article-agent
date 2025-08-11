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
- **attachments:** File processing and text extraction

### LLM Provider Integration
- **OpenRouter API:** Primary LLM access point
- **Model:** openrouter/moonshotai/kimi-k2:free (default)
- **Configuration:** Via dspy_factory.py setup utility
- **API Key:** Stored in .env file as OPENROUTER_API_KEY

## Existing Infrastructure

### Scoring System (li_article_judge.py)
- **Architecture:** Comprehensive 180-point evaluation system
- **Categories:** 8 major scoring categories with weighted criteria
- **Data Models:** Pydantic-based ScoreResultModel and ArticleScoreModel
- **Integration:** Direct Python import for dynamic criteria access

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

## DSPy Implementation Patterns

### Signature Design
```python
class ArticleSignature(dspy.Signature):
    """Specific task description for LLM"""
    
    input_field = dspy.InputField(desc="Detailed input description")
    output_field = dspy.OutputField(desc="Expected output format")
```

### Module Architecture
```python
class ArticleModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.component = dspy.ChainOfThought(Signature)
    
    def forward(self, **inputs):
        return self.component(**inputs)
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
2. **Word Count Check:** Validate length requirements
3. **Quality Scoring:** Evaluate against criteria
4. **Feedback Analysis:** Extract improvement instructions
5. **Iterative Refinement:** Improve based on feedback

### Output Validation
1. **Structure Check:** Ensure proper article format
2. **Length Validation:** Confirm 2000-2500 word range
3. **Quality Verification:** Achieve ≥89% score
4. **Final Review:** Complete article ready for publication

## Performance Considerations

### Optimization Strategies
- **Model Reuse:** Cache DSPy model instances
- **Criteria Caching:** Avoid repeated criteria parsing
- **Incremental Improvement:** Targeted changes vs. complete rewrites
- **Early Termination:** Stop when targets achieved

### Resource Management
- **API Rate Limits:** Respect OpenRouter usage limits
- **Memory Usage:** Efficient handling of large articles
- **Processing Time:** Balance quality with generation speed
- **Cost Optimization:** Minimize unnecessary LLM calls

## Development Environment

### File Structure
```
/
├── memory-bank/           # Project documentation and context
├── li_article_judge.py    # Existing scoring system (DO NOT MODIFY)
├── dspy_factory.py        # LLM provider setup utility
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (API keys)
├── articles/              # Sample articles for testing
└── [new implementation files]
```

### Configuration Management
- **Environment Variables:** API keys and configuration
- **Default Settings:** Sensible defaults for all parameters
- **User Customization:** Configurable targets and preferences
- **Debug Mode:** Enhanced logging and intermediate output

## Quality Assurance

### Testing Strategy
- **Unit Tests:** Individual component validation
- **Integration Tests:** End-to-end article generation
- **Scoring Tests:** Verify scoring system integration
- **Performance Tests:** Measure generation speed and quality

### Validation Framework
- **Input Validation:** Ensure valid outlines and drafts
- **Output Validation:** Verify article quality and format
- **Criteria Compliance:** Check adherence to scoring requirements
- **Word Count Compliance:** Validate length constraints

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

## Monitoring and Debugging

### Logging Strategy
- **Progress Tracking:** Iteration-by-iteration progress
- **Error Logging:** Comprehensive error capture
- **Performance Metrics:** Generation time and quality trends
- **Debug Output:** Detailed intermediate results

### Metrics Collection
- **Success Rate:** Percentage of articles achieving targets
- **Iteration Count:** Average iterations to reach goals
- **Quality Trends:** Score improvements over time
- **Performance Benchmarks:** Speed and efficiency metrics
