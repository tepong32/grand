# Media storage for GSO asset records

## Recommendation

For a production deployment, keep uploaded evidence in a private object-storage bucket owned and administered by the LGU, separate from the Namecheap web account. Django remains the authority for who may see each record and file. Store the object key, case/asset relationship, uploader, original filename, content type, size, checksum, and timestamps in the application database; validate uploads in Django before accepting them.

These uploads can include asset condition photos, signed forms, employee names, and signatures. Treat them as restricted operational records. Keep public access disabled, require encryption in transit and at rest, use role-limited service credentials, enable versioning or an equivalent recovery control, and define retention, backup, export, and deletion rules with the LGU records officer. The LGU should own the provider account, billing relationship, keys, and data export rights; the cloud provider acts under the LGU's instructions and contract rather than owning the records.

For the initial release, private object storage with time-limited, permission-checked downloads is sufficient. A CDN is not required for a small internal asset workflow. If download speed later becomes an issue, use a private origin and authenticated edge delivery; never make the evidence bucket public simply to enable caching. Use thumbnails for list views and keep originals available through the protected download route.

## Options compared

| Option | Advantages | Costs and risks | Fit |
| --- | --- | --- | --- |
| Namecheap shared-hosting disk | Simplest initial setup; Django can write to a directory outside the web root. | Storage and backups share the hosting provider's operational boundary; app and media availability fail together; quota and recovery options depend on the hosting plan. Must confirm the configured path is not web-accessible. | Acceptable for a prototype or low-risk pilot with separate backups, not the preferred long-term evidence store. |
| LGU-managed cloud object storage | Separate credentials and storage lifecycle from the web host; durable object API over HTTPS; easier backup, export, and migration planning. | Requires procurement and configuration, credentials management, retention policy, and review of data location, privacy terms, and support. | Recommended production baseline. Choose a provider/region only after LGU data-governance review. |
| Object storage plus private CDN | Can speed repeated downloads while retaining a private origin, if the CDN enforces signed/authorized access and cache policy. | More configuration and cache invalidation complexity; signed links can be shared until expiry; caching sensitive documents creates additional controls and audit requirements. | Later optimization if real usage shows a need; not the starting point for signed forms and disposal evidence. |
| LGU-operated NAS/VPS or separate media server, reached by remote mount/VPN/SFTP | Physical or administrative control may be closer to the LGU; can fit existing on-premise backup and network policies. | The LGU then owns patching, monitoring, capacity, off-site backup, disaster recovery, remote connectivity, certificates, and uptime. A network mount or remote-access tunnel adds an operational dependency and can become a single point of failure. | Consider only if the LGU has an IT team and an approved hosting/DR arrangement to operate it. Django should still use a documented storage interface, not ad hoc file transfer. |

## Cloud provider notes

Two plausible object-storage patterns are:

- **AWS S3 with CloudFront:** put the bucket in an approved region, block public access, and let CloudFront reach it through Origin Access Control. Django can issue short-lived signed CloudFront URLs after checking the user's application permissions. AWS documents private S3 origins through OAC and signed URLs for private content. Singapore is an available AWS region, and CloudFront has an edge location in Manila; neither fact by itself establishes that a deployment meets LGU data-location policy.
- **Cloudflare R2:** private buckets can be accessed through S3-compatible APIs, and Django can issue expiring presigned URLs for direct upload/download. Cloudflare says presigned URLs use the R2 S3 API endpoint rather than a custom domain. Its location hints are best-effort and do not guarantee a specific country or residency boundary. Do not use a public bucket for these records.

For this app's signed forms and evidence, the AWS private-origin pattern is the clearer option if a CDN becomes necessary. Without a demonstrated need for edge caching, select the approved object store and keep downloads private; avoid paying for or operating CDN behavior that does not improve the users' workflow. R2 may be a simpler S3-compatible storage option where the LGU accepts its residency and control model, but confirm those requirements first.

## Namecheap and application boundary

Namecheap's shared-hosting documentation describes deploying Django through its cPanel Python application/WSGI setup. That can host the web application, but it should not be treated as the media archive merely because it can serve the site. Confirm the exact shared-hosting plan's disk quotas, backup/restore scope, HTTPS egress to the chosen object provider, request-size limits, and whether a CDN product is enabled and what it caches. A site CDN does not automatically provide private object authorization or a records retention policy.

Keep a storage adapter boundary in Django so the current private filesystem implementation can be replaced by an S3-compatible backend without changing asset/disposal workflows. Avoid mounting a remote file share into shared hosting unless the host explicitly supports it and the LGU can operate and secure the connection. For uploads, Django should enforce user authorization, allowed formats and size, and case association. For downloads, check access on every request and then return a short-lived link or stream the object. Do not put permanent public URLs in the database.

## Government data and procurement checks

Before choosing a provider, have the LGU's DPO, ICT/security staff, records officer, and procurement/legal reviewers classify the actual files and approve the provider, region, contract, retention, breach handling, audit access, backups, portability, and exit plan. This document is an architecture recommendation, not a legal or procurement determination.

Executive Order No. 119 (2026) encourages LGUs to adopt its government-cloud provisions; its specific mandatory scope and data-classification requirements should not be casually applied to an LGU without review. It assigns agencies responsibility for security safeguards when using cloud services and describes controls by classification. The Data Privacy Act IRR requires controller/processor terms to address matters such as processing location and safeguards. Obtain current LGU guidance before storing employee-linked documents or selecting an offshore region. In particular, do not assume an APAC setting or a nearby CDN edge proves Philippine data residency.

## References

- [Namecheap: Deploying Django on shared servers](https://www.namecheap.com/support/knowledgebase/article.aspx/10753/2182/how-to-deploy-a-django-application-on-shared-servers/)
- [Namecheap: Working with Python applications](https://www.namecheap.com/support/knowledgebase/article.aspx/10048/2182/how-to-work-with-python-app/)
- [AWS: Private content and Origin Access Control](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-overview.html)
- [AWS: CloudFront signed URLs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-signed-urls.html)
- [AWS: Regions](https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html)
- [AWS: CloudFront features and edge locations](https://aws.amazon.com/cloudfront/features/)
- [Cloudflare R2: Public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/)
- [Cloudflare R2: Presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/)
- [Cloudflare R2: Data location](https://developers.cloudflare.com/r2/reference/data-location/)
- [Executive Order No. 119, s. 2026](https://lawphil.net/statutes/execord/eo2026/eo_119_2026.html)
- [National Privacy Commission: Data Privacy Act Implementing Rules and Regulations](https://privacy.gov.ph/implementing-rules%20regulations-data-privacy-act-2012/)
