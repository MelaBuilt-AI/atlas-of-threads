# Privacy information

Updated September 19, 2026. Atlas of Threads is maintained by MelaBuilt AI.
This page describes the current desktop application and optional Connected Atlas.
Version 0.4.0 includes the optional Connected Atlas alongside the local desktop.

## Personal Atlas

Inquiries, graph history, Field Notes and local Knowledge Capsules are stored on
your computer. Launching the local application does not upload that store.
The application serves its interface on the local loopback address. Provider
credentials remain with the provider's own tools and authentication settings.
The application does not include an advertising or behavioral-analytics SDK.

## Release checks and downloads

Packaged desktop applications automatically check a small public release manifest
at startup and when checking for updates. This request goes to
`downloads.atlasofthreads.com`, hosted through Cloudflare. It includes the Atlas
version in its user-agent header and the network metadata ordinarily visible to
an HTTPS server, such as the requesting IP address. It does not include inquiry
contents, provider credentials or a Personal Atlas store identifier.

An update downloads the selected platform package when you choose to update.
The existing desktop interface does not offer a separate switch to disable the
startup manifest check. These ordinary network requests are distinct from
uploading inquiry content.

## AI collaborators and remote connections

When you explicitly request a continuation or guide discussion, Atlas passes the
reviewed or selected context to the collaborator you configured. That provider's
own authentication, data handling and usage terms apply. Atlas does not make a
provider's service private merely because the Atlas store is local.

A remote agent connection contacts the SSH destination you enter and trust.
Provider setup or sign-in can open the provider's own website or terminal. Local
agent discovery does not invoke a model. Remote setup displays proposed firewall
commands rather than applying firewall changes automatically.

Consult the privacy information for your selected provider, such as
[OpenAI](https://openai.com/policies/privacy-policy/),
[Anthropic](https://www.anthropic.com/legal/privacy), or
[xAI](https://x.ai/legal/privacy-policy). Other configured agents may use different
providers; inspect their configuration and policies before sharing context.

## The optional Connected Atlas

The online service uses GitHub sign-in to identify an owner. Pairing a Personal
Atlas registers that device; pairing alone does not upload inquiries. The service
stores account, device, session and consent records needed for connected actions.
Authentication secrets are kept separately from public inquiry data.

Publishing uploads the explicitly reviewed inquiry snapshot for public reading
and download. Text you choose to publish can contain personal information, so
review it carefully. Private guide conversations, provider credentials and local
evidence files are not automatically included in the publication export.

Capsule destination review sends the displayed payload to the service for
validation; sending commits delivery to the audience shown in the review.
Directed Capsules are restricted to participants; open invitations and offerings
are available to signed-in visitors. Receiving a Capsule does not invoke an agent.
Accepting a private excerpt does not publish a public doorway. Public full-return
inquiries and their doorway connections require separate review and consent.

The service stores publications, delivery/decision history, stars, following,
reports and blocks needed for these features. Optional activity sharing starts
off and expires when inactive; it does not report your private chamber or
conversation. The service and hosting provider can process ordinary request
metadata for operation and security. See
[GitHub's privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement)
and [Cloudflare's privacy policy](https://www.cloudflare.com/privacypolicy/).

You can disconnect or revoke paired devices without deleting local inquiries.
Publication withdrawal removes availability through the service but cannot recall
copies another person already downloaded. Revoking an account session is not a
request to delete every publication or historical delivery. Do not assume a
record has been erased merely because access was revoked.

## Files, links and music

Local music files selected in the browser stay in that browser tab. If you choose
an external music stream or follow an external link, your browser contacts that
host and its privacy practices apply. Portable exports and local Capsule files
are saved locally; sending them through another service is your separate choice.

## Questions

Contact the maintainer through the public GitHub project for general questions.
For a vulnerability or accidental exposure of private data, use the repository's
private security-advisory reporting flow rather than posting the data in an issue.
