# Grok Generative AI Conversation 
**Releases:**
- version 0.1.1: update translations ​​and bug fixes.
- version 0.1.2: update for HACS    
___
## Installation

### HACS
Click this link to install **Grok Generative AI Conversation** via **HACS**

[![Open your Home Assistant instance and add a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Pajeronda&repository=grok_generative_ai_conversation&category=integration)

___  
## 🎯 Concept: LLM as Intelligent Router
Home Assistant integration for xAI Grok with intelligent smart home command routing

A sophisticated Home Assistant custom integration that combines the conversational intelligence of xAI's Grok models with Home Assistant's native smart home capabilities.


Unlike traditional LLM integrations that either handle everything directly or nothing at all, this integration uses **Grok as an intelligent router** that makes smart decisions about how to handle user requests.

## 🔄 The Smart Pipeline

### Core Architecture

```
User Input → LLM (Grok) → Intelligent Decision:
├── "Conversational Query" → Direct Response
└── "Smart Home Command" → [[HA_LOCAL: {"text": "extracted command"}]]
                              ↓
                         Home Assistant Native Processing
                              ↓
                         ┌─ Assist Intent Recognition
                         └─ Tools Fallback (if needed)
```

### Pipeline Phases
<div align="center">
<img width="50%" height="auto" alt="immagine" src="https://github.com/user-attachments/assets/7bef7e43-abd9-4634-b297-331070ad3547" />
</div>

#### 1. **LLM Analysis Phase** 🧠
- Grok analyzes the user's input in any language
- Corrects ASR (Automatic Speech Recognition) errors
- Decides whether the request is:
  - **Conversational**: General questions, chat, information requests
  - **Smart Home Command**: Device control, status queries, automation requests

#### 2. **Command Extraction & Tagging** 🏷️
For smart home commands, Grok:
- Extracts the essential command from conversational context
- Wraps it in a special tag: `[[HA_LOCAL: {"text": "turn on living room light"}]]`
- Examples:
  - *"Hey, could you maybe turn on the living room light?"* → `[[HA_LOCAL: {"text": "turn on living room light"}]]`
  - *"Che ne dici di illuminare il soggiorno?"* → `[[HA_LOCAL: {"text": "accendi le luci in soggiorno"}]]`

#### 3. **Native Home Assistant Processing** 🏠
The extracted command flows through Home Assistant's native systems:
- **Assist Pipeline**: Uses HA's built-in intent recognition
- **Native Tools**: Leverages Home Assistant's comprehensive device control
- **Multi-language Support**: Benefits from HA's localized intent processing

#### 4. **Intelligent Fallback** 🔧
If native intent recognition fails:
- Automatically falls back to Home Assistant's LLM tools system
- Uses `ConversationEntityFeature.CONTROL` for native tool integration
- Maintains context and provides robust command handling

## ✨ Key Benefits

### **🌍 Universal Language Support**
- Process commands in any language
- Grok handles translation and context understanding
- Home Assistant processes in the most appropriate format

### **🎯 Context-Aware Processing**
- Maintains conversational context while delegating control
- Distinguishes between chat and commands intelligently
- Preserves natural conversation flow

### **🔧 Robust & Reliable**
- Leverages Home Assistant's mature smart home ecosystem
- Provides fallback mechanisms for edge cases
- Combines AI intelligence with proven automation systems

### **🎵 ASR Error Correction**
- Automatically corrects voice recognition errors
- Improves voice control reliability
- Handles ambiguous or unclear commands gracefully

## 🚀 Why This Approach?

Traditional integrations face a dilemma:
- **Direct LLM Control**: Powerful but unreliable, requires custom tool implementations
- **Intent-Only Systems**: Reliable but limited, poor natural language understanding

**Our Solution**: Best of both worlds
- Grok's advanced language understanding for routing decisions
- Home Assistant's proven smart home control for execution
- Seamless integration that feels natural and works reliably

## 🏗️ Technical Implementation

### Core Components
- **Conversation Entity**: Handles the LLM routing logic
- **Tag-Based Pipeline**: Streams responses and detects smart home commands
- **Native Integration**: Uses Home Assistant's conversation framework
- **Fallback System**: Employs HA's built-in tool calling as backup

### Configuration Options
- **Dual Mode Operation**: Tag-based pipeline or direct tools mode
- **Custom Prompts**: Personalize the routing behavior
- **Model Parameters**: Fine-tune temperature, tokens, and other settings
- **Multi-Agent Support**: Configure different behaviors per use case

## 🎪 Example Scenarios

```
🗣️ "Turn on the lights"
   → [[HA_LOCAL: {"text": "turn on the lights"}]]
   → HA Intent Recognition
   → Lights activated ✅

🗣️ "What's the weather like?"
   → Direct conversational response from Grok 🌤️

🗣️ "Could you maybe dim the bedroom lights to 30%?"
   → [[HA_LOCAL: {"text": "dim bedroom lights to 30%"}]]
   → HA Tools (if intent fails)
   → Lights dimmed ✅

🗣️ "Potresti spegnere la TV in salotto?" (Italian)
   → [[HA_LOCAL: {"text": "spegni TV salotto"}]]
   → HA Processing
   → TV turned off ✅
```

---

*This integration represents a new paradigm in smart home AI: intelligent routing that preserves the strengths of both conversational AI and native home automation systems.*
---
Readme update 2025-10-09
