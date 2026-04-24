# Pull Request — KnowLaw AI Team

## 📋 Description
<!-- Briefly explain what you changed and why -->


## 🔗 Related Task
<!-- Which feature or bug does this PR address? -->


---

## ✅ Author Checklist (done by the person opening the PR)

### Code Quality
- [ ] My code runs without errors
- [ ] I tested the feature manually before submitting
- [ ] I did not leave any debug `print()` statements in the code
- [ ] I did not hardcode any file paths (used `os.path.join` instead)
- [ ] I did not include any passwords, secrets, or `.env` files

### Documentation
- [ ] I added comments to explain any complex logic
- [ ] I updated `README.md` if I added a new file or feature
- [ ] My commit messages are clear and descriptive

### Database & Schema
- [ ] If I changed a database table, I updated both `auth.py` AND `database_setup.py`
- [ ] I did not delete any columns that other files depend on

### Git Hygiene
- [ ] My branch name is descriptive (e.g. `sara-contract-fix`, not `branch1`)
- [ ] I am merging into `main` from my personal branch (not directly editing main)
- [ ] I pulled the latest `main` before opening this PR

---

## 🔍 Peer Review Checklist (done by the reviewer — a DIFFERENT team member)

### Functionality
- [ ] I pulled this branch and tested it locally
- [ ] The feature works as described in the PR description
- [ ] No existing features are broken by this change

### Code Review
- [ ] The code is readable and easy to understand
- [ ] No obvious logic errors or bugs
- [ ] No sensitive data (passwords, local paths) is exposed
- [ ] Functions are not unnecessarily duplicated

### Quality Factors
- [ ] **Correctness** — The code does what it says it does
- [ ] **Consistency** — Follows the same style as the rest of the project
- [ ] **Security** — No passwords, tokens, or hardcoded paths
- [ ] **Completeness** — No missing features or half-finished code
- [ ] **Clarity** — Comments and variable names are understandable

---

## 📝 Reviewer Notes
<!-- The reviewer writes their comments here -->


## ✅ Reviewer Decision
- [ ] **Approved** — Ready to merge ✅
- [ ] **Changes Requested** — See comments above ❌

---

*Reviewer must be a different team member from the author.*
*Merging without approval is not allowed.*
