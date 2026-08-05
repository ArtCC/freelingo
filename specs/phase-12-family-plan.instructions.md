---
description: "Functional specification for FreeLingo Phase 12: Family Plan. Defines the roles, flows, access rules, and product lifecycle without implementation details."
---

# Phase 12: Family Plan

> **Status: Planned.** This functionality has not been developed or implemented yet.

## Objective

The Family Plan allows one person to pay for a Premium subscription and share access with their household. Each person uses their own FreeLingo account and keeps their languages, study plans, progress, conversations, flashcards, preferences, memory, and personal data completely independent.

The owner manages the group and its billing. Invitees receive Premium access while they belong to a family group with active access, without sharing any learning data with the rest of the group.

## Concepts

- **Family group**: set of accounts that share Premium access funded by an owner.
- **Owner**: account that creates the group and assumes payment. Always belongs to the group.
- **Member**: invited account that receives access from an active family group.
- **Invitation**: personal request sent by the owner to an email address to add an account to the group.
- **Premium access**: the user's right to use paid features. It has a single clear state for each user, regardless of whether it comes from an individual or family plan.
- **Billing**: payment relationship with Stripe. It can belong to a user on an individual plan or to a group on a family plan.

## Scope

- A group supports up to five accounts in total, including the owner.
- An owner can invite up to four additional people.
- Each person can belong to only one family group at a time.
- Each user with Premium access can have only one access source at a time: an individual plan or family group.
- The Family Plan has no trial period. The owner and members receive active family access only after payment is confirmed.
- The Family Plan is only available when Stripe billing is enabled.
- Email must be available to deliver invitations. If it is not, invitations that cannot reach their recipients cannot be created.

## Pricing Presentation On The Landing Page

The landing page presents the commercial offer before the user subscribes. The goal is for a person to clearly distinguish between learning alone and sharing Premium with their household.

- The pricing section is shown only when billing is available and the visitor does not have Premium access.
- If at least one family option is enabled, the section shows two tabs: **Individual** and **Family**.
- The **Individual** tab is shown initially and contains the Free, Premium monthly, and Premium yearly plans, along with a feature comparison.
- The **Family** tab contains only the available family options, monthly, yearly, or both depending on the active offer. It does not mix free or individual plans.
- The Family tab visibly states that the plan covers up to five independent accounts, including the payer, and summarizes the group-specific benefits: separate accounts, private progress, and invitation management by the owner.
- Each family card shows its price, billing period, and call to action to subscribe to the Family Plan.
- The yearly family plan is identified as the best-value option when available.
- If no family option is enabled, the landing page retains the individual-plan presentation without tabs or references to the family offer.

For a visitor without a session, calls to action direct them to registration while preserving the selected option. For an authenticated user without Premium access, they start checkout for the selected option. A user with Premium access, individual or family, must not see the subscription offer on the landing page again.

## Premium Access

### Separation Between Billing And Access

Billing and Premium access are different concepts and must not be mixed.

- Billing describes the payment agreement and its status with Stripe. On an individual plan it belongs to the user; on a family plan it belongs to the group and is managed by the owner.
- Premium access only describes whether an account can use Premium features at this time.
- A billing status, such as a pending or failed payment, must not require each learning feature to interpret Stripe rules. The application transforms the billing result into a clear access state for each affected user.

### Single User State

Each user has a single Premium access state:

- **No access**: can use free features, but not Premium features.
- **Trialing**: can use Premium features while the trial period lasts.
- **Active**: can use Premium features.

Each user also has a single access source:

- **None**: does not have Premium access.
- **Individual**: pays for their own plan.
- **Family owner**: pays for the group plan.
- **Family member**: receives access from another person's group.

The source is used to present the interface and apply management permissions. It does not change learning permissions: a person with active or trialing access has the same Premium features, regardless of their source.

The trialing state can only have an individual source. The Family Plan does not offer trials: both the owner and members receive either active access or no access.

Technical billing states are not user access states. A pending, failed, unpaid, canceled, or incomplete payment is used solely to manage the owner's billing and decide the next access transition. Learning features never receive or interpret those states: they only receive active, trialing, or no access.

### Common Premium Rule

All Premium features exclusively consult the user's single access state.

- Active or trialing access allows chat, voice conversation, listening and reading exercises, Premium-associated limits, and any future paid feature. Authenticated memory management remains available independently of Premium access.
- No access blocks those features, except explicitly defined product exceptions, such as a limited demo for users without Premium.
- No feature should recalculate on its own whether the user belongs to a group, is an owner, or whether Stripe has updated a payment.

### Access Synchronization

Actions that change billing or membership update the access of affected users consistently:

1. When an individual plan is activated, the user receives active or trialing access with an individual source.
2. When a family plan is activated, the owner receives active access with a family-owner source.
3. When an invitation to an active group is accepted, the invitee receives active access with a family-member source.
4. When group access ends due to effective cancellation, the group is dissolved, its invitations are revoked, and all of its members move to no access and a none source. A payment incident freezes the group without dissolving it and removes Premium access from all of its members.
5. When a member leaves or is removed, they lose their family access.
6. When a member deletes their account, their membership is removed and their seat is released. An owner cannot delete their account while maintaining a group with active billing.

These transitions must be atomic from the user's perspective: there must not be a window in which a member appears Premium in one part of the application and free in another.

## Group Creation

1. A user can select the Family Plan only if they do not belong to an operational family group, do not have active or trialing individual access, do not have a pending individual charge, and do not have another pending family checkout.
2. They complete the Stripe payment process.
3. After payment confirmation, their family group is created or activated.
4. The payer becomes the owner and occupies the first seat.
5. The owner receives Premium access and can invite up to four accounts.

The group is only considered available when payment is confirmed. The application must not show an active group or grant family access for an abandoned or pending checkout.

## Owner Management

The owner has a Family Plan section within account settings.

From there they can:

- View the group status and their Premium access.
- View available seats and the member list.
- Distinguish active members and pending invitations.
- Send an invitation by email address.
- Resend a pending or expired invitation.
- Revoke a pending invitation.
- Remove a member from the group.
- Access billing management for their family plan.
- Cancel the family plan.

The owner cannot remove themselves. To stop funding the group, they must cancel the family plan. Cancellation retains access until the applicable end date and then dissolves the group.

## Subscription In Settings

The subscription section in settings shows each user information that is correct for their role, without exposing payment information to members.

### Common Information

An owner and a member with family access see:

- That they have an active Family Plan.
- That their Premium access comes from a family group.
- Their role in the group: owner or member.
- The end date when the plan has been canceled and retains access until that date.

### Owner

The owner also sees:

- The subscribed option, monthly or yearly.
- The amount, the next billing date, or the end date if they have canceled the plan.
- The billing status and any action required to recover a payment.
- Used and available seats, members, and pending invitations.
- Actions to manage billing, cancel the plan, and invite or manage members.

### Member

The member also sees:

- That the plan is managed and paid for by the owner.
- A non-sensitive identifier for the owner.
- The option to leave the group.

The member does not see the amount, payment method, invoices, detailed billing status, or the owner's administrative controls. If the group loses access, the section informs them that family access has ended and allows them to choose an individual plan or create a new group when appropriate.

## Invitations

An invitation belongs to a group, is addressed to a specific email address, and can only be used once.

- The invitation states who is inviting, that Premium access is obtained through the group, and when it expires.
- The invitation expires 48 hours after it is sent.
- A pending invitation reserves a seat to prevent the owner from exceeding the group limit.
- Duplicate invitations cannot be sent to the same address while a valid pending invitation exists.
- The owner can revoke it before it is accepted.
- A revoked, expired, or used invitation does not grant access and releases the seat it reserved.
- Resending an invitation creates a new 48-hour invitation and replaces the previous reservation, without accumulating reserved seats.
- Accepting an invitation is a final action: before joining, it is validated again that the invitation is valid, the email matches, the group remains active, a seat is available, and the user does not have an incompatible subscription. Only then does the seat become occupied by the accepting account.

## Invitee Flow

The invitation link must work both for people with an account and for new people.

### Invitee With An Account

1. The link shows the group and owner without exposing private data from other members.
2. If they are not signed in, they must authenticate with the account whose email matches the invitation.
3. They confirm that they want to join.
4. They receive family Premium access and see the group in their settings.

### Invitee Without An Account

1. The link shows a valid invitation and directs them to registration.
2. The registration email is tied to the invitation and must not be changeable during that flow.
3. After verifying or completing the required registration, the account accepts the invitation.
4. The user ends at an understandable destination: their family settings or onboarding if they still need to configure their learning.
5. The invitation state must be retained during registration and onboarding so that the user does not lose confirmation or have to reuse the link.

### Invitee Restrictions

An invitation cannot be accepted by someone who:

- Already belongs to another family group.
- Has an active or trialing individual plan.
- Has a pending individual subscription that could become a charge.
- Uses an account with an email different from the recipient's.
- Attempts to use an expired, revoked, or already used invitation.

The interface must explain the reason and offer a clear path forward, for example managing the existing subscription, signing in with the correct account, or requesting a new invitation.

## Members

A member can:

- See that their Premium access comes from a family group.
- See the owner's name or non-sensitive identifier and their access status.
- Leave the group voluntarily.
- Continue using their account and all learning data independently.

A member cannot:

- Manage family billing.
- Invite, remove, or modify other members.
- Become owner through an invitation or the owner's departure.
- Keep family Premium access after leaving or being removed.

When leaving or being removed, the user always moves to no Premium access and a none source. Their learning data remains intact. Only afterward can they subscribe to an individual plan if they wish.

## Relationship With The Individual Plan

The Family Plan and the Individual Plan do not overlap for the same account.

- A person with an active or trialing individual plan must resolve it before creating a group or accepting an invitation.
- A person who belongs to a family group, including a frozen group, cannot subscribe to an individual plan.
- A person who leaves a group can subscribe to an individual plan after their family access and membership have been removed.
- Canceled or ended subscriptions do not by themselves block a new plan choice, as long as there is no access or pending charge.
- The application must proactively prevent duplicate charges and not rely only on the interface to do so.

## Billing And Lifecycle

The owner is solely responsible for group billing.

- Stripe determines the payment status of the family plan.
- The application transforms the payment status into the single access state of the owner and members consistently.
- The Family Plan does not offer a trial period.
- A scheduled cancellation retains active access for current members until the effective end date shown to the owner, but immediately blocks new invitations and acceptances. On that date, the group is dissolved, invitations are revoked, memberships are removed, and the owner and members move to no access and a none source.
- A failed, unpaid, or unrecoverable payment freezes the group and removes family access: the owner and members move to no access and a none source, but the group, its memberships, and its invitations are preserved.
- An incomplete or abandoned checkout does not grant family access to any account.
- When family access ends or is lost, all members stop receiving family Premium access at the same time.
- In the event of a pending or failed payment, the application shows the real status and only offers recovery actions to the owner.
- A frozen group remains frozen until the owner resolves the payment or definitively cancels the Family Plan. If the payment is successfully recovered, the group becomes active again and the owner and its current members regain active Premium access.
- While the group is frozen, the owner can remove members. Removed members lose their membership and can subscribe to an individual plan.
- A dissolved group is not reactivated. If the owner wants to subscribe to a Family Plan again, they create a new group and invite their members again.
- It must not be possible to subscribe to or pay for two family plans for the same owner through repeated actions, simultaneous tabs, or network retries.

## Group Dissolution

A group is dissolved when its access ends due to effective cancellation. A payment incident that removes Premium freezes the group without dissolving it. It is not dissolved before a paid period ends.

- Revokes pending invitations.
- Removes family membership from all members.
- Removes family Premium access from the owner and members.
- Does not delete accounts, progress, conversations, study plans, or personal data from any member.
- The owner cannot delete their account while the group has active billing. They must cancel the plan and wait for dissolution.

## Interface States

The experience must avoid ambiguous states and always show a clear primary action.

- **No plan**: allows choosing Individual or Family.
- **Active owner**: shows members, seats, invitations, and billing.
- **Active member**: shows family access, owner, and the option to leave.
- **Pending invitation**: shows recipient, expiration, resend, and revoke actions to the owner.
- **Pending payment or payment issue**: informs about the problem and directs only the owner to recover it.
- **Ended group**: informs about lost access and allows the former owner to choose Individual or create a new Family Plan when appropriate.
- **Invalid invitation**: explains whether it has expired, been revoked, already used, or belongs to another email.

The payment confirmation page must recognize confirmed family access just as it recognizes individual access. No user with active family access must see a free-plan or pending-payment interface because of consulting an incorrect state.

## Privacy And Security

- Invitations are validated against the recipient email and do not reveal sensitive information before authentication.
- Invitation links are personal, expire, and stop working after use or revocation.
- Members cannot access billing, payment information, or the owner's administrative controls.
- The owner cannot view members' learning content, conversations, memories, private profile, or preferences.
- All group actions verify role and membership on the server.
- Concurrent operations must not allow exceeding seats, accepting a revoked invitation, or creating duplicate charges.
- Deleting a member account removes them from the group and frees their seat. Deleting the owner account is blocked while active family billing exists.
