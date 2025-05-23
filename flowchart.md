flowchart TD
    %% Agent 1
    A1[Agent 1 - DataCollector]
    T1[Tool: API Fetcher - fetch_data\nPurpose: retrieve raw external data]
    A1 --> T1
    T1 --> A2

    %% Agent 2
    A2[Agent 2 - Preprocessor]
    T2[Tool: Data Cleaner - clean_data\nPurpose: sanitize and normalize data]
    A2 --> T2
    T2 --> A3

    %% Agent 3
    A3[Agent 3 - Analyzer]
    T3[Tool: Analyzer Toolkit - analyze_trends\nPurpose: extract patterns and metrics]
    A3 --> T3
    T3 --> A4

    %% Agent 4
    A4[Agent 4 - DecisionMaker]
    T4[Tool: Rule Engine - make_decision\nPurpose: apply logic to produce actions]
    A4 --> T4
    T4 --> A5

    %% Agent 5
    A5[Agent 5 - Reporter]
    T5[Tool: Report Generator - generate_report\nPurpose: produce final summary report]
    A5 --> T5