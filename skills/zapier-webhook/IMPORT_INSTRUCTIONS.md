# Zapier JSON Import Instructions

**Note:** Zapier doesn't have a direct "paste JSON" import feature in the standard UI. However, I've created these JSON files as **reference configurations** to make manual setup easier.

---

## ⚠️ Reality Check

Zapier's import options are:
1. **Zap Templates** (shared links)
2. **Transfer between accounts** (requires Zapier Teams)
3. **Manual creation** (fastest for you)

**No direct JSON paste import exists in the UI.**

---

## ✅ Best Approach: Use JSON as Setup Guide

The JSON files I created show **exactly** what to configure. Follow these steps:

---

## 🚀 Zap 1: Create Calendar Event from Linear

### Reference: `zap1-linear-to-calendar.json`

**Manual Setup (5 minutes):**

1. **Create Zap:** https://zapier.com/app/zaps → "+ Create"

2. **Step 1 - Trigger:**
   - App: **Linear**
   - Event: **New Issue**
   - Team: **a previous employer**
   - Test trigger → Continue

3. **Step 2 - Filter:**
   - App: **Filter by Zapier**
   - Condition 1: `Priority Name` **contains** `High`
   - Add OR condition: `Priority Name` **contains** `Urgent`
   - Continue

4. **Step 3 - Action:**
   - App: **Google Calendar**
   - Event: **Create Detailed Event**
   - **Calendar:** primary
   - **Summary:** `[TODO] ` + Insert `Title` from Linear
   - **Description:**
     ```
     Linear Issue ID: [Insert Linear ID]
     Priority: [Insert Priority Name]
     Estimate: [Insert Estimate] points
     
     [Insert Description]
     
     Link: [Insert URL]
     ```
   - **Start Date & Time:** 
     - Date: Insert `Due Date` (or tomorrow's date)
     - Time: `09:00`
   - **End Date & Time:**
     - Same date
     - Time: `11:00` (or calculate based on estimate)
   - **All Day:** No
   - **Color:** `5` (Yellow)
   - **Timezone:** Europe/London

5. **Test & Publish**

---

## 🔄 Zap 2: Update Calendar When Status Changes

### Reference: `zap2-linear-update-calendar.json`

**Manual Setup (8 minutes):**

1. **Create Zap:** https://zapier.com/app/zaps → "+ Create"

2. **Step 1 - Trigger:**
   - App: **Linear**
   - Event: **Updated Issue**
   - Team: **a previous employer**
   - Test trigger → Continue

3. **Step 2 - Find Calendar Event:**
   - App: **Google Calendar**
   - Action: **Find Event**
   - **Calendar:** primary
   - **Search Term:** `Linear Issue ID: ` + Insert `ID` from Linear
   - **Search By:** Description
   - Test → Continue

4. **Step 3 - Format Status to Emoji:**
   - App: **Formatter by Zapier**
   - Event: **Lookup Table**
   - **Input:** Insert `State Name` from Linear
   - **Lookup Table:**
     ```
     Todo → ⚪ TODO
     In Progress → 🔵 IN PROGRESS
     Done → ✅ DONE
     Canceled → ❌ CANCELED
     Backlog → ⚫ BACKLOG
     ```
   - **Default:** `⚪ TODO`
   - Continue

5. **Step 4 - Format Status to Color:**
   - App: **Formatter by Zapier**
   - Event: **Lookup Table**
   - **Input:** Insert `State Name` from Linear
   - **Lookup Table:**
     ```
     Todo → 5
     In Progress → 9
     Done → 10
     Canceled → 8
     Backlog → 7
     ```
   - **Default:** `5`
   - Continue

6. **Step 5 - Update Calendar Event:**
   - App: **Google Calendar**
   - Action: **Update Event**
   - **Calendar:** primary
   - **Event ID:** Insert `Id` from Step 2 (Find Event)
   - **Summary:** Insert `Output` from Step 3 + `: ` + Insert `Title` from Linear
   - **Color:** Insert `Output` from Step 4
   - Test → Continue

7. **Publish**

---

## 🎯 Exact Field Mappings

### Linear Fields You'll See:
- `1. Id` → Linear issue ID (e.g., NE-123)
- `1. Title` → Issue title
- `1. Description` → Issue description
- `1. Priority Label` / `Priority Name` → Priority text
- `1. State Name` → Status (Todo, In Progress, Done, etc.)
- `1. URL` → Link to Linear issue
- `1. Estimate` → Story points
- `1. Due Date` → Due date

### Calendar Color Codes:
- `5` = Yellow (Todo, High priority)
- `7` = Cyan (Backlog)
- `8` = Gray (Canceled)
- `9` = Blue (In Progress)
- `10` = Green (Done)
- `11` = Red (Urgent)

---

## 📋 Quick Reference Card

**Copy this for quick lookup while building:**

### Status → Emoji Mapping
```
Todo          → ⚪ TODO
In Progress   → 🔵 IN PROGRESS
Done          → ✅ DONE
Canceled      → ❌ CANCELED
Backlog       → ⚫ BACKLOG
```

### Status → Color Mapping
```
Todo          → 5 (Yellow)
In Progress   → 9 (Blue)
Done          → 10 (Green)
Canceled      → 8 (Gray)
Backlog       → 7 (Cyan)
```

---

## 🧪 Testing

### Test Zap 1:
1. Create Linear issue: Title "Test Calendar", Priority "High"
2. Wait 15 min
3. Check calendar for `[TODO] Test Calendar`

### Test Zap 2:
1. Change issue status to "In Progress"
2. Wait 15 min
3. Check calendar - title should update to `🔵 IN PROGRESS: Test Calendar`

---

## ❓ Where Did You Get Stuck?

Tell me the exact step number and I'll give you more detailed help for that specific step.

**Example:** "Step 3 of Zap 1 - I don't see 'Due Date' in the Linear fields"

---

## 💡 Pro Tip: Screenshot Each Step

As you build, take screenshots of your field mappings. If something breaks later, you can compare to the working setup.

---

**Estimated Time:**
- Zap 1: 5-7 minutes
- Zap 2: 8-12 minutes
- Total: ~15 minutes

**Need help with a specific step?** Tell me where you're stuck!
