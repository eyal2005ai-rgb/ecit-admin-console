# One-time setup: register ECIT Admin Console in your tenant

ECIT Admin Console signs in through an **app registration that you create and own in your own
Microsoft 365 tenant**. ECIT has no app registration, no access to your tenant and no copy of
your settings. You can delete the registration at any time, and the app then stops working
for that tenant.

You do this **once per tenant**. If you manage several tenants (MSP), repeat it in each tenant
and save one connection per tenant in the app.

Who can do it: a **Global Administrator**, or an **Application Administrator** for the
registration plus a **Privileged Role Administrator** to grant consent.

---

## Option A: Entra admin center (about 5 minutes)

1. Open **entra.microsoft.com → Identity → Applications → App registrations → New registration**.
2. **Name:** `ECIT Admin Console`
3. **Supported account types:** *Accounts in this organizational directory only (Single tenant)*.
4. **Redirect URI:** platform **Public client/native (mobile & desktop)**, value `http://localhost`.
   Click **Register**.
5. **Authentication → Advanced settings → Allow public client flows: Yes** → **Save**.
6. **API permissions → Add a permission → Microsoft Graph → Delegated permissions**, add:

   | Permission | Why |
   |---|---|
   | `User.Read` | Show who is signed in |
   | `User.Read.All` | Search and read the employee |
   | `User.EnableDisableAccount.All` | Block sign-in |
   | `User-PasswordProfile.ReadWrite.All` | Reset password |
   | `User.RevokeSessions.All` | Revoke all sessions |
   | `UserAuthenticationMethod.ReadWrite.All` | Remove MFA methods |

7. Click **Grant admin consent for &lt;your tenant&gt;** and confirm. All rows should show a
   green tick.
8. On the **Overview** page copy:
   - **Application (client) ID**
   - **Directory (tenant) ID**

No client secret or certificate is needed: it is a desktop (public client) app and every action
runs with the permissions of the admin who signs in.

## Option B: PowerShell script (about 1 minute)

`create-app-registration.ps1` (in the same folder as this guide) does steps 1 to 7 for you and prints the two IDs.

```powershell
# Once per computer, if you don't have the Microsoft Graph module yet:
Install-Module Microsoft.Graph.Applications, Microsoft.Graph.Identity.SignIns -Scope CurrentUser

# Then, for each tenant:
.\create-app-registration.ps1 -TenantId contoso.onmicrosoft.com
```

You sign in as a Global Administrator; the script creates the registration, adds the six
permissions, grants admin consent and shows the Application (client) ID and Directory (tenant) ID.

---

## Add the connection in the app

1. Open ECIT Admin Console and click **Connections…** (top bar).
2. **Name:** anything that helps you recognise the tenant, for example the customer's name.
3. **Tenant:** the Directory (tenant) ID, or a verified domain such as `contoso.onmicrosoft.com`.
4. **Application (client) ID:** the ID you copied.
5. Click **Save**, choose the tenant at the top of the window and click **Sign in**.

Connections are saved only on your computer (in the app's settings file). They contain IDs, not
passwords or secrets.

## Roles the admin who signs in needs

Permissions say what the *app* may do; Entra roles say what the *admin* may do. The app can never
do more than the signed-in admin is allowed to. To run an offboarding the admin needs at least:

- **User Administrator**: block sign-in, reset password, revoke sessions for regular users
- **Authentication Administrator**: remove MFA methods of regular users
- To offboard another **admin** account: **Privileged Authentication Administrator** (or Global Administrator)

If a role is missing, that step fails with "Access denied", the other steps still run, and the
report shows exactly which step failed.

## Common sign-in messages

| Message | Fix |
|---|---|
| Application ID not found in this tenant (AADSTS700016) | Wrong client ID, or the connection points to a different tenant than the one where you registered the app. |
| Public client flows are off (AADSTS7000218) | Step 5: Allow public client flows → Yes. |
| Redirect URI mismatch (AADSTS50011) | Step 4: add `http://localhost` under Mobile and desktop applications. |
| Permissions not approved (AADSTS65001 / AADSTS90094) | Step 7: Grant admin consent. |
| Account not in this tenant (AADSTS50020) | Sign in with an admin account of the tenant in the connection. |

## Remove access

Entra admin center → **App registrations** → **ECIT Admin Console** → **Delete**. Then delete the
connection in the app (Connections… → Delete).
