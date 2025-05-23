graph TD
    %% Main Orchestrator
    O[Orchestrator]
    
    %% Customer Service Agent
    CSA[Customer Service Agent]
    CST1[Tool: Check Stock]
    CST2[Tool: Get Item Price]
    CST3[Tool: Search Quote History]
    CSA --> CST1
    CSA --> CST2
    CSA --> CST3
    
    %% Inventory Agent
    IA[Inventory Agent]
    IT1[Tool: Check Stock]
    IT2[Tool: Create Transaction]
    IT3[Tool: Get All Inventory]
    IT4[Tool: Get Supplier Delivery Date]
    IA --> IT1
    IA --> IT2
    IA --> IT3
    IA --> IT4
    
    %% Quoting Agent
    QA[Quoting Agent]
    QT1[Tool: Get Item Price]
    QT2[Tool: Check Stock]
    QT3[Tool: Search Quote History]
    QT4[Tool: Get Cash Balance]
    QA --> QT1
    QA --> QT2
    QA --> QT3
    QA --> QT4
    
    %% Sales Agent
    SA[Sales Agent]
    ST1[Tool: Check Stock]
    ST2[Tool: Create Transaction]
    ST3[Tool: Get Item Price]
    ST4[Tool: Generate Financial Report]
    SA --> ST1
    SA --> ST2
    SA --> ST3
    SA --> ST4
    
    %% Finance Agent
    FA[Finance Agent]
    FT1[Tool: Get Cash Balance]
    FT2[Tool: Generate Financial Report]
    FT3[Tool: Create Transaction]
    FA --> FT1
    FA --> FT2
    FA --> FT3
    
    %% Workflow Connections
    O --> CSA
    O --> IA
    O --> QA
    O --> SA
    O --> FA
    
    %% Agent Interactions
    CSA -.-> IA
    CSA -.-> QA
    QA -.-> IA
    QA -.-> FA
    SA -.-> IA
    SA -.-> FA
    IA -.-> FA
    
    %% Legend
    subgraph Legend
        L1[Agent]
        L2[Tool]
        L3[Data Flow]
    end