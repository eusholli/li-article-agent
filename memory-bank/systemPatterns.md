# System Patterns - LinkedIn Article Generator

## Architecture Overview

### Enhanced Core System Design with Runtime Model Selection
```
Input (Outline/Draft) 
    ↓
Model Selection & Configuration (component-specific LLM models)
    ↓
Dynamic Criteria Extraction (from li_article_judge.py)
    ↓
Article Generation (DSPy Module with configurable model + word count guidance)
    ↓
Combined Quality + Length Scoring (li_article_judge.py with configurable model + word_count field)
    ↓
Unified Target Achievement Check (quality_achieved AND length_achieved)
    ↓
Smart Feedback Analysis (targets scoring weaknesses for length adjustments)
    ↓
Iterative Refinement Loop (combines quality and length improvements with optimal models)
    ↓
Target Achievement (≥89% score + 2000-2500 words achieved simultaneously)
```

### Runtime Model Selection Architecture
```
Command-Line Arguments
    ↓
Model Configuration Resolution (fallback hierarchy)
    ↓
Enhanced Factory Pattern (dspy_factory.py)
    ↓
Model Instance Creation & Caching
    ↓
Component-Specific LM Assignment
    ↓
DSPy Module Initialization (with dedicated models)
    ↓
Execution with Optimal Models per Operation
```

### New Draft Scoping Pattern (Latest Enhancement)
- **Pre-Generation Analysis:** Comprehensive understanding of input before generation
- **Key Insights Extraction:** Main theme, key points, target audience, core message
- **Content Gap Identification:** Areas needing expansion for complete LinkedIn article
- **Consistency Tracking:** Maintain fidelity to original draft throughout iterations
- **Context Preservation:** Original draft context flows through entire pipeline

### Key Design Patterns

#### 1. Enhanced Factory Pattern for Model Management
- **Model Instance Creation:** `get_model_instance(model_name)` creates and caches LM instances
- **Component LM Creation:** `create_component_lm(model_name)` wraps models in ConfiguredLM
- **Intelligent Fallbacks:** `get_fallback_model()` provides graceful degradation
- **Performance Caching:** `_model_instance_cache` prevents redundant model initialization
- **Backward Compatibility:** Existing `setup_dspy_provider()` unchanged

#### 2. Component-Specific Model Selection Pattern
```python
class ComponentWithModel(dspy.Module):
    def __init__(self, model_name=None):
        super().__init__()
        if model_name:
            # Use component-specific model
            self.lm = create_component_lm(model_name)
            self.module = dspy.ChainOfThought(Signature, lm=self.lm)
        else:
            # Fall back to global DSPy configuration
            self.module = dspy.ChainOfThought(Signature)
```

#### 3. Dynamic Criteria Integration Pattern
- **Runtime Import:** Load scoring criteria from li_article_judge.py at execution time
- **Criteria Parsing:** Extract weights, questions, and scales automatically
- **Adaptive Generation:** Adjust article focus based on current criteria weights
- **Change Detection:** Automatically adapt when criteria are modified

#### 4. Iterative Improvement Loop Pattern
```python
while not (score >= target_score and word_count_valid):
    article = generate_or_improve(outline, feedback, previous_version, models)
    score_result = score_article(article, judge_model)
    feedback = extract_improvement_guidance(score_result)
    iteration += 1
    if iteration > max_iterations:
        break
```

#### 5. Multi-Constraint Optimization Pattern
- **Dual Targets:** Simultaneously optimize for score and word count
- **Constraint Balancing:** Prioritize improvements that address both constraints
- **Trade-off Management:** Handle conflicts between quality and length requirements
- **Model Optimization:** Use optimal models for each constraint type

#### 6. Feedback-Driven Refinement Pattern
- **Structured Feedback:** Convert scoring results into actionable improvement instructions
- **Priority Ranking:** Focus on lowest-scoring criteria first
- **Incremental Improvement:** Make targeted changes rather than complete rewrites
- **Model-Aware Feedback:** Consider model capabilities when generating improvement instructions

#### 7. Cost Optimization Pattern
- **Strategic Model Selection:** Use expensive models only where they add most value
- **Free Model Defaults:** Default to free models for cost-conscious usage
- **Mixed Model Workflows:** Combine free and paid models based on operation importance
- **Budget-Quality Balance:** Optimize for best quality within budget constraints

## Component Relationships

### Core Modules
1. **Enhanced DSPy Factory:** Model instance management and caching
2. **CriteriaExtractor:** Dynamically loads and parses scoring criteria
3. **ArticleGenerator:** Creates and improves articles using configurable DSPy models
4. **ArticleScorer:** Evaluates articles using configurable scoring models
5. **RAG Retriever:** Web search and context retrieval with configurable models
6. **WordCountManager:** Manages length constraints and adjustments
7. **FeedbackProcessor:** Converts scores into improvement instructions
8. **IterationController:** Orchestrates the improvement loop with optimal models

### Data Flow Patterns
```
COMMAND-LINE ARGUMENTS
    ↓ (model selection)
Enhanced Factory Pattern
    ↓ (model instances)
SCORING_CRITERIA (li_article_judge.py)
    ↓ (import & parse)
CriteriaExtractor
    ↓ (criteria summary)
ArticleGenerator (with generator_model)
    ↓ (generated article)
WordCountManager
    ↓ (word count validation)
LinkedInArticleScorer (with judge_model)
    ↓ (score results)
FeedbackProcessor
    ↓ (improvement instructions)
ArticleGenerator (next iteration with optimal model)
```

### Model Selection Flow
```
CLI Arguments (--generator-model, --judge-model, --rag-model, --model)
    ↓
Model Resolution (component-specific or fallback)
    ↓
Factory Pattern (get_model_instance, create_component_lm)
    ↓
Model Instance Cache (performance optimization)
    ↓
Component Initialization (with dedicated models)
    ↓
Execution (optimal model per operation)
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

### Enhanced Module Composition Pattern with Model Selection
```python
class CompositeModuleWithModels(dspy.Module):
    def __init__(self, model1_name=None, model2_name=None):
        super().__init__()
        
        # Component-specific models or fallback to global
        if model1_name:
            lm1 = create_component_lm(model1_name)
            self.sub_module_1 = dspy.ChainOfThought(Signature1, lm=lm1)
        else:
            self.sub_module_1 = dspy.ChainOfThought(Signature1)
            
        if model2_name:
            lm2 = create_component_lm(model2_name)
            self.sub_module_2 = dspy.ChainOfThought(Signature2, lm=lm2)
        else:
            self.sub_module_2 = dspy.ChainOfThought(Signature2)
    
    def forward(self, inputs):
        # Orchestrate sub-modules with optimal models
        result1 = self.sub_module_1(**inputs)
        result2 = self.sub_module_2(input=result1.output)
        return combined_result
```

### Model-Aware Component Pattern
```python
class ModelAwareComponent(dspy.Module):
    def __init__(self, model_name=None):
        super().__init__()
        self.model_name = model_name
        
        if model_name:
            # Use dedicated model instance
            self.lm = create_component_lm(model_name)
            self.component = dspy.ChainOfThought(Signature, lm=self.lm)
        else:
            # Use global DSPy configuration
            self.component = dspy.ChainOfThought(Signature)
    
    def forward(self, **inputs):
        return self.component(**inputs)
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

### Enhanced Caching Strategy
- **Criteria Caching:** Cache parsed criteria to avoid repeated parsing
- **Model Instance Caching:** `_model_instance_cache` prevents redundant model creation
- **Component LM Caching:** Reuse ConfiguredLM instances across operations
- **Result Caching:** Store intermediate results for debugging
- **Factory Pattern Optimization:** Single model instance creation per unique model name

### Incremental Improvement Strategy
- **Targeted Changes:** Focus improvements on specific weak areas
- **Minimal Edits:** Preserve good content while fixing problems
- **Progressive Enhancement:** Build quality incrementally
- **Model-Optimized Improvements:** Use best model for each improvement type
- **Cost-Aware Iterations:** Balance improvement quality with API costs

## Integration Patterns

### Loose Coupling with li_article_judge.py
- **Import-Based Integration:** Use Python imports rather than API calls
- **Dynamic Loading:** Load criteria at runtime for flexibility
- **Interface Stability:** Depend on stable data structures (SCORING_CRITERIA)
- **Model-Agnostic Scoring:** Scoring system works with any configured model

### Enhanced Extensibility Pattern
- **Plugin Architecture:** Easy addition of new improvement modules
- **Configurable Constraints:** Adjustable word count and score targets
- **Modular Scoring:** Support for different scoring systems
- **Model Plugin System:** Easy addition of new LLM providers and models
- **Component Model Configuration:** Each component can use different models independently
- **Fallback Chain:** Graceful degradation through model hierarchy

## Monitoring and Debugging Patterns

### Enhanced Progress Tracking Pattern
```python
class ProgressTracker:
    def track_iteration(self, iteration, score, word_count, improvements, models_used):
        # Log progress metrics
        # Track model performance per operation
        # Identify improvement trends
        # Detect convergence or divergence
        # Monitor cost vs. quality trade-offs
```

### Enhanced Debug Information Pattern
- **Iteration Logging:** Track changes between iterations
- **Model Usage Tracking:** Log which models used for each operation
- **Score Breakdown:** Detailed category-by-category analysis with model attribution
- **Improvement Tracing:** Map feedback to actual changes made
- **Cost Tracking:** Monitor API usage and costs per model
- **Performance Metrics:** Track model-specific response times and quality

## Scalability Patterns

### Enhanced Batch Processing Pattern
- **Multiple Articles:** Process multiple outlines in parallel
- **Shared Model Instances:** Reuse cached models across articles and operations
- **Optimized Resource Allocation:** Distribute expensive models efficiently
- **Result Aggregation:** Collect and analyze batch results with model performance metrics

### Advanced Configuration Management Pattern
- **Environment-Specific Settings:** Different targets for different use cases
- **User Preferences:** Customizable quality and length preferences
- **Model Configuration Profiles:** Predefined model combinations for different use cases
- **Cost Budget Management:** Automatic model selection based on budget constraints
- **A/B Testing Support:** Compare different model combinations and generation strategies
- **Performance Profiling:** Track model effectiveness across different content types
