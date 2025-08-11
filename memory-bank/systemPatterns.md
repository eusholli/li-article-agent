# System Patterns - LinkedIn Article Generator

## Architecture Overview

### Enhanced Core System Design
```
Input (Outline/Draft) 
    ↓
Draft Scoping & Analysis (NEW: DraftScopingSignature)
    ↓ (scoped_analysis + original_draft)
Dynamic Criteria Extraction (from li_article_judge.py)
    ↓
Enhanced Article Generation (DSPy Module with draft context)
    ↓
Quality Scoring (li_article_judge.py)
    ↓
Feedback Analysis & Improvement Planning
    ↓
Context-Aware Iterative Refinement Loop (maintains original draft fidelity)
    ↓
Target Achievement (≥89% score + 2000-2500 words + consistency)
```

### New Draft Scoping Pattern (Latest Enhancement)
- **Pre-Generation Analysis:** Comprehensive understanding of input before generation
- **Key Insights Extraction:** Main theme, key points, target audience, core message
- **Content Gap Identification:** Areas needing expansion for complete LinkedIn article
- **Consistency Tracking:** Maintain fidelity to original draft throughout iterations
- **Context Preservation:** Original draft context flows through entire pipeline

### Key Design Patterns

#### 1. Dynamic Criteria Integration Pattern
- **Runtime Import:** Load scoring criteria from li_article_judge.py at execution time
- **Criteria Parsing:** Extract weights, questions, and scales automatically
- **Adaptive Generation:** Adjust article focus based on current criteria weights
- **Change Detection:** Automatically adapt when criteria are modified

#### 2. Iterative Improvement Loop Pattern
```python
while not (score >= target_score and word_count_valid):
    article = generate_or_improve(outline, feedback, previous_version)
    score_result = score_article(article)
    feedback = extract_improvement_guidance(score_result)
    iteration += 1
    if iteration > max_iterations:
        break
```

#### 3. Multi-Constraint Optimization Pattern
- **Dual Targets:** Simultaneously optimize for score and word count
- **Constraint Balancing:** Prioritize improvements that address both constraints
- **Trade-off Management:** Handle conflicts between quality and length requirements

#### 4. Feedback-Driven Refinement Pattern
- **Structured Feedback:** Convert scoring results into actionable improvement instructions
- **Priority Ranking:** Focus on lowest-scoring criteria first
- **Incremental Improvement:** Make targeted changes rather than complete rewrites

## Component Relationships

### Core Modules
1. **CriteriaExtractor:** Dynamically loads and parses scoring criteria
2. **ArticleGenerator:** Creates and improves articles using DSPy
3. **WordCountManager:** Manages length constraints and adjustments
4. **FeedbackProcessor:** Converts scores into improvement instructions
5. **IterationController:** Orchestrates the improvement loop

### Data Flow Patterns
```
SCORING_CRITERIA (li_article_judge.py)
    ↓ (import & parse)
CriteriaExtractor
    ↓ (criteria summary)
ArticleGenerator
    ↓ (generated article)
WordCountManager
    ↓ (word count validation)
LinkedInArticleScorer (li_article_judge.py)
    ↓ (score results)
FeedbackProcessor
    ↓ (improvement instructions)
ArticleGenerator (next iteration)
```

## DSPy Module Architecture

### Signature Design Pattern
```python
class OptimizedSignature(dspy.Signature):
    """Clear, specific task description"""
    
    # Input fields with detailed descriptions
    input_field = dspy.InputField(desc="Specific description of expected input")
    
    # Output fields with validation criteria
    output_field = dspy.OutputField(desc="Specific description of expected output")
```

### Module Composition Pattern
```python
class CompositeModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.sub_module_1 = dspy.ChainOfThought(Signature1)
        self.sub_module_2 = dspy.ChainOfThought(Signature2)
    
    def forward(self, inputs):
        # Orchestrate sub-modules
        result1 = self.sub_module_1(**inputs)
        result2 = self.sub_module_2(input=result1.output)
        return combined_result
```

## Quality Assurance Patterns

### Validation Pipeline Pattern
1. **Input Validation:** Ensure outline/draft meets minimum requirements
2. **Generation Validation:** Verify article structure and completeness
3. **Word Count Validation:** Check length constraints
4. **Quality Validation:** Score against criteria
5. **Output Validation:** Ensure final article meets all requirements

### Error Handling Pattern
```python
try:
    result = generate_article(outline)
except GenerationError:
    # Fallback to simpler generation approach
    result = fallback_generation(outline)
except ScoringError:
    # Use cached scoring or manual review
    result = handle_scoring_failure(article)
```

## Performance Optimization Patterns

### Caching Strategy
- **Criteria Caching:** Cache parsed criteria to avoid repeated parsing
- **Model Caching:** Reuse DSPy model instances across iterations
- **Result Caching:** Store intermediate results for debugging

### Incremental Improvement Strategy
- **Targeted Changes:** Focus improvements on specific weak areas
- **Minimal Edits:** Preserve good content while fixing problems
- **Progressive Enhancement:** Build quality incrementally

## Integration Patterns

### Loose Coupling with li_article_judge.py
- **Import-Based Integration:** Use Python imports rather than API calls
- **Dynamic Loading:** Load criteria at runtime for flexibility
- **Interface Stability:** Depend on stable data structures (SCORING_CRITERIA)

### Extensibility Pattern
- **Plugin Architecture:** Easy addition of new improvement modules
- **Configurable Constraints:** Adjustable word count and score targets
- **Modular Scoring:** Support for different scoring systems

## Monitoring and Debugging Patterns

### Progress Tracking Pattern
```python
class ProgressTracker:
    def track_iteration(self, iteration, score, word_count, improvements):
        # Log progress metrics
        # Identify improvement trends
        # Detect convergence or divergence
```

### Debug Information Pattern
- **Iteration Logging:** Track changes between iterations
- **Score Breakdown:** Detailed category-by-category analysis
- **Improvement Tracing:** Map feedback to actual changes made

## Scalability Patterns

### Batch Processing Pattern
- **Multiple Articles:** Process multiple outlines in parallel
- **Shared Resources:** Reuse models and criteria across articles
- **Result Aggregation:** Collect and analyze batch results

### Configuration Management Pattern
- **Environment-Specific Settings:** Different targets for different use cases
- **User Preferences:** Customizable quality and length preferences
- **A/B Testing Support:** Compare different generation strategies
