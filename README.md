# LinkedIn Article Generator

This is a DSPy implementation that takes a draft article or outline of an article, and outputs the best performing LinkedIn article possible, as defined by the scoring in li_article_judge.py.

It should generate an article that using the scoring criteria as defined in li_article_judge.py as a guide on how to write it.  
It should then get a score and based on the improvement feedback received continue to edit the article until the article achieves world class status which is a score >= 89%.

When drafting the versions of the article, always pass in the suggested improvements alongside the previous version of the article.  On each cycle print out the progress and the resulting draft article version.  