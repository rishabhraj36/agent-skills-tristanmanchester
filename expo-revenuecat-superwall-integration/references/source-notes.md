# Source Notes for Maintainers

This skill was revised as v2 on 2026-03-08.

Key documentation reviewed while preparing this version:

## Agent Skills resources

- agentskills.io home and what-are-skills pages
- agentskills.io specification
- BEST_PRACTICES_FOR_WRITING_AND_USING_SKILLS_MD_FILES.md
- the bundled PDF guide about building skills

Key skill-specific takeaways applied here:

- keep `SKILL.md` focused
- push detailed material into `references/`
- make the description explicit about what and when
- keep the folder in kebab-case and include `SKILL.md` exactly
- include examples, references, validation help, and a zipped deliverable

## Superwall resources

Reviewed areas included:

- Expo install and development-build requirements
- RevenueCat integration guide
- subscription-state tracking
- user management
- webhook and original-app-user-id troubleshooting
- placement troubleshooting
- analytics and `useSuperwallEvents`
- `CustomPurchaseControllerProvider` docs

## RevenueCat resources

Reviewed areas included:

- Expo and React Native installation
- identifying customers
- restoring purchases
- restore behaviour
- trusted entitlements
- observer mode / `purchasesAreCompletedBy`
- Test Store and sandbox guidance
- Billing Client 8 restore issue notes

## Intent of v2

The main improvement over v1 is that the skill is now decision-led rather than happy-path-only. It explicitly teaches the agent to reason about:

- architecture choice
- identity model
- restore policy
- Android base plans and offers
- iOS UUID and server-notification consequences
- observability
- test coverage
