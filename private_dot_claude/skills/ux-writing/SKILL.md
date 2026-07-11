---
name: ux-writing
description: "Use whenever creating, editing, or reviewing user-facing UI text: headings, labels, buttons, links, forms, empty states, errors, confirmations, toasts, onboarding, loading states, and tooltips. Trigger when building UI, reviewing UI strings, or replacing placeholder copy."
---

# UX Writing

Write UI copy that helps users complete tasks quickly and confidently.

## Principles

1. Clarity over cleverness.
2. User goal over system implementation.
3. Specific action over generic labels.
4. Consistent terms for the same concept.
5. Helpful recovery over blame.
6. Accessible wording over visual-only cues.
7. Short enough for the UI, complete enough to be useful.

## Required copy patterns

### Buttons and CTAs
Use verb + object when possible.

Good:
- Save changes
- Create project
- Invite teammate
- Delete invoice

Avoid:
- Submit
- OK
- Continue, unless the next step is truly generic
- Click here

### Error messages
Use: what happened + how to fix it.

Good:
- Payment failed. Try another card or contact your bank.
- Email must include @.
- Upload failed. Choose a file under 10 MB.

Avoid:
- Something went wrong
- Invalid input
- Error 403
- You entered the wrong value

### Empty states
Use: what is empty + why it matters + next action.

Good:
- No projects yet. Create your first project to organize your work.
- No results found. Try a different keyword or clear filters.

Avoid:
- Nothing here
- No data
- Empty

### Confirmations
Name the action and consequence.

Good:
- Delete 3 files?
- This cannot be undone.
- Buttons: Delete files / Keep files

Avoid:
- Are you sure?
- OK / Cancel for destructive actions

### Forms
Use visible labels. Use placeholders only for examples, not as the only label.

Good:
- Label: Email address
- Placeholder: name@example.com
- Helper: We’ll send the receipt here.

### Success messages
Confirm what changed.

Good:
- Changes saved
- Invite sent
- Profile updated

Avoid:
- Success!
- Done, when the completed action is unclear

### Loading states
Say what the app is doing, not that the user must wait.

Good:
- Uploading 3 photos…
- Preparing your export… This can take a few minutes.

Avoid:
- Loading…
- Please wait
- Checking…, without saying what is being checked

### Tooltips
Add information the label does not already say. Never put required information only in a tooltip.

Good:
- On an "Archive on close" checkbox: Archived chats stay searchable and can be reopened anytime.

Avoid:
- Restating the label ("Archive on close: archives the chat when you close it")

## Final UI copy review

Before finishing any UI task:
1. List all visible strings added or changed.
2. Replace placeholder, vague, or system-centered text.
3. Check buttons use specific verbs.
4. Check errors include a recovery path.
5. Check empty states include a next step.
6. Check terms are consistent across the screen.
7. Flag any copy that needs product/brand input.
