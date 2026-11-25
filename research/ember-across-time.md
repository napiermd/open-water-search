# Muse Ember across time: what one request can carry and what it costs

Checked on 2026-11-24 against Meta's documentation at dev.meta.ai. Token measurements come from this project's own billed usage logs and are labelled as such. No Meta API call was made for this note.

## Answer

- **Several images in one request.** One request can carry up to 50 images as separate `input_image` blocks, with text blocks between them. More than 50 returns HTTP 400. Each inline image can be up to 50 MB. [Media understanding](https://dev.meta.ai/docs/media-understanding)
- **Image tokens.** Meta documents that image cost scales with resolution and publishes two reference points (a 1×1 image is about 3 tokens, a ~1280px image is about 1,300 to 1,500). In this project's logs, every 224px crop with its "Crop N:" label added exactly 70 input tokens across 1,951 requests. An `input_image.detail` field exists (`low`, `high`, `auto`, `original`, default `auto`) and its effect on tokens is undocumented. [Media understanding](https://dev.meta.ai/docs/media-understanding), [Responses schemas](https://dev.meta.ai/docs/api-reference/responses/schemas)
- **Video.** Ember lists video as an input type. The documented path is an MP4 through `input_video` or `input_file`, with an optional `fps` field. Meta publishes no token cost per frame or per second for video on the Model API, so its price for a 3-second clip is unverified. [Muse Ember](https://dev.meta.ai/docs/muse-ember), [Media understanding](https://dev.meta.ai/docs/media-understanding)
- **Caching and batch.** Caching is automatic and matches from the first token of the prompt forward. Crops differ in every request, so only the fixed prompt can be cached, and the logs show about 22 cached tokens per request. The pricing page lists no batch price or batch discount, and the API reference has no batch endpoint. [Prompt caching](https://dev.meta.ai/docs/prompt-caching), [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits), [API reference](https://dev.meta.ai/docs/api-reference)
- **Rate limits.** The published limit for `muse-ember-1.0` is 3,000 requests per minute and 4,000,000 tokens per minute per team. The docs describe no separate limit for credit-funded teams. The team's actual limits appear on the dashboard Limits page, which I could not open. [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits), [Rate limits help](https://dev.meta.ai/help/usage-and-limits/rate-limits)
- **Same object, and is it a person.** The docs cover pointing, boxes and counting inside one image. They say nothing about matching one object across several images. The only first-party feature documented to keep an object's identity across frames is SAM 3.1 video tracking. [Media understanding](https://dev.meta.ai/docs/media-understanding), [SAM overview](https://dev.meta.ai/docs/sam/overview)
- **Cost of 3 crops instead of 1 per flag.** Two extra 224px crops add 140 input tokens, which is $0.000014 per flag, or $14 per million flags. On the largest logged run that is about +34% (+$0.091 on $0.269) provided the answer still holds one verdict per flag.
- **Cheapest way to show a flag across 3 seconds.** Put the three 224px crops of that flag into the request the flag already travels in, in time order with a short text label before each, and keep one verdict per flag in the schema.

## Which pages I could reach

All of these loaded today and are cited below.

- Muse Ember model page, Choose a model, Models, Overview
- Pricing and rate limits
- Image, video, and audio understanding
- Prompt caching and token counting
- Responses API guide, Responses API reference index, Count input tokens reference
- File handling, Files API reference, Files schemas
- Error handling, Structured output, Reasoning
- SAM overview
- Help Center pages for usage tracking, rate limits, billing and billing setup
- Terms of Service

Pages with a qualification.

- The Responses schemas page failed at its plain URL. It loaded at the same URL with a `team_id` query parameter that a search result supplied, and the crawl was dated today. [Responses schemas](https://dev.meta.ai/docs/api-reference/responses/schemas)
- `https://dev.meta.ai/docs/batch` and `https://dev.meta.ai/docs/api-reference/batches` were guesses on my part and returned "not accessible". Neither URL is linked from any page I read, so they may simply not exist.
- `https://dev.meta.ai/llms.txt` timed out.
- The dashboard Limits and Usage pages need a signed-in team. I did not open them.

The media understanding page is written with Muse Spark as the named model. The Ember page states that Ember accepts the same request body as Muse Spark and links to that page for image understanding. I treat the image and video limits there as applying to Ember on that basis. Meta publishes no Ember-specific table of media limits. [Muse Ember](https://dev.meta.ai/docs/muse-ember)

## 1. Several images in a stated order, and limits

- A request may include several image blocks. On the Responses API they are `input_image` blocks inside a user message. [Media understanding](https://dev.meta.ai/docs/media-understanding)
- The cap is 50 images per request and it is enforced with HTTP 400. Requests are also bounded by payload size and the context window. A PDF contributes at most its first 50 page images toward the same budget. [Media understanding](https://dev.meta.ai/docs/media-understanding)
- A single message accepts multiple content blocks, and user blocks include `input_text`, `input_image`, `input_file` and `input_video`. This is the documented basis for placing a text label before each image. [Responses API](https://dev.meta.ai/docs/protocols/responses)
- Order is the order of blocks in the `content` array. The docs give no explicit statement about how the model treats image order. **Unverified** as a documented guarantee. This project already numbers crops with "Crop N:" labels and reads verdicts back by number.
- Per-image size is 50 MB inline (50,000,000 bytes) and 1 GiB through the Files API. Accepted types are JPEG, PNG, GIF, WebP and ICO. [Media understanding](https://dev.meta.ai/docs/media-understanding), [File handling](https://dev.meta.ai/docs/file-handling)
- The schema reference shows a 20,971,520-character maximum on `image_url` for one of the two `input_image` definitions. That figure is smaller than the 50 MB stated in the guide. A 224px JPEG is far below both. [Responses schemas](https://dev.meta.ai/docs/api-reference/responses/schemas)
- No total-bytes limit for a normal synchronous request is stated beyond the per-file limits. Two narrower limits are documented. A background request body is capped at 1 MiB, and a `store: true` request with large inline base64 media can return HTTP 413 at persistence (the documented example is about 16 MB). `store` defaults to true. [Error handling](https://dev.meta.ai/docs/error-handling), [Responses API](https://dev.meta.ai/docs/protocols/responses)
- The context window is 1,048,576 tokens. A request above 200,000 input tokens is billed at the long-context rates for all of its tokens. [Muse Ember](https://dev.meta.ai/docs/muse-ember), [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)

## 2. How an image becomes tokens

What Meta documents.

- Image cost scales with resolution. A 1×1 image adds about 3 tokens. A ~1280px image adds about 1,300 to 1,500 tokens. No formula, patch size or maximum resolution is given. [Media understanding](https://dev.meta.ai/docs/media-understanding)
- Token contribution depends on the model and version, the prompt template, media preprocessing and image resolution. Meta advises measuring with `POST /v1/responses/input_tokens` and re-measuring after a model or media-processing change. [Prompt caching and token counting](https://dev.meta.ai/docs/prompt-caching)
- That endpoint tokenizes only. It generates no output and records no generation usage. [Prompt caching and token counting](https://dev.meta.ai/docs/prompt-caching)
- Meta's pages disagree on whether that count includes Meta's injected system context. The token counting page says the count includes it because it occupies the model's context. The pricing page says injected tokens are unbilled and excluded from both `usage` and the token-counting endpoints. Comparing differences between two counts sidesteps the question. [Prompt caching and token counting](https://dev.meta.ai/docs/prompt-caching), [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)
- `input_image` has an optional `detail` field with values `low`, `high`, `auto` and `original`, defaulting to `auto`. The reference calls it render detail. It gives no resolutions and no token effect for any value. The media understanding guide never mentions the field. **Unverified** what each value does on Ember. [Responses schemas](https://dev.meta.ai/docs/api-reference/responses/schemas)
- The guide's Chat Completions example response shows 272 prompt tokens for a request that carries a 1280px-wide image, which conflicts with the 1,300 to 1,500 figure on the same page. I treat the example as illustrative. [Media understanding](https://dev.meta.ai/docs/media-understanding)

What this project's billed usage shows. This is measurement from local logs, outside Meta's documentation.

- Flag-check requests send a 65-token prompt, then for each flag a "Crop N:" text block and one 224×224 JPEG with `detail` unset. Across 1,951 requests in five runs (10,039 crops), billed `input_tokens` equals 65 + 70 × crops with no exception. Source files are `repo/open-water-search/runs/verify-*/**/checks-redacted.jsonl` and the request shape is in `repo/open-water-search/probe/flag_check.py`.
- Overview requests in `runs/scale-run/calls-redacted.jsonl` send one image resized to a 1,000px long side. Billed input is 769 tokens for 1000×562, 913 for 1000×666 and 1,021 for 1000×759.
- **My inference, unverified by Meta.** Those four sizes fit one token per 28×28-pixel block with each side rounded, plus a fixed prompt cost. 1000×562 gives 36×20 = 720, 1000×666 gives 36×24 = 864, 1000×759 gives 36×27 = 972, each with the same 49-token remainder. A 224px crop gives 8×8 = 64, leaving 6 tokens for the label. Meta's "~1280px is 1,300 to 1,500" figure also fits (1280×853 gives 46×30 = 1,380).
- By that fit a 448px crop would cost about 256 tokens and a 672×224 strip of three crops about 192, the same as three separate 224px crops. Treat both numbers as estimates until measured with the token-count endpoint. The project has never sent an image above 1,000px, so any downscaling cap is unknown.

## 3. Video and frame sequences

- Ember's input types are text, image, video, audio and PDF. [Muse Ember](https://dev.meta.ai/docs/muse-ember)
- Video understanding accepts MP4. Upload through the Files API with purpose `user_data` and reference the file with `input_file`, or send an `input_video` block with a `video_url` (public URL or base64 data URL) or a `file_id`. The model reads the visual sequence and the embedded audio together. [Media understanding](https://dev.meta.ai/docs/media-understanding)
- `input_video` has an optional `fps` number for frame sampling. The default is a backend-chosen rate that the docs leave unstated. [Responses schemas](https://dev.meta.ai/docs/api-reference/responses/schemas)
- Inline video shares the 50 MB inline limit and uploaded video the 1 GiB limit. [File handling](https://dev.meta.ai/docs/file-handling)
- No page gives a token cost per frame or per second of video on the Model API, a maximum duration, or a frame cap. **Unverified.**
- The docs define no frame-sequence input type. A sequence of stills goes in as ordinary `input_image` blocks under the 50-image cap.
- One first-party number exists for a different model and host. Meta's page on hosted Muse Spark Open says Baseten's video encoder samples at most 96 frames per clip and that a 720p clip costs about 144 tokens per second. That describes Muse Spark Open on Baseten and tells us nothing certain about Ember on the Model API. [Muse Spark Open, run inference](https://dev.meta.ai/docs/muse-spark-open/deploy)

## 4. Cached input and batch

Caching.

- Caching is automatic prefix caching. The server compares the start of the tokenized prompt with recently cached state, serves the matching leading tokens from cache, and computes everything after the first difference fresh. No flag, key or breakpoint is required. [Prompt caching](https://dev.meta.ai/docs/prompt-caching)
- A prefix is cacheable when a recent request began with the same tokens. Stable content belongs first and variable content last. The docs state no minimum prefix length. [Prompt caching](https://dev.meta.ai/docs/prompt-caching)
- `prompt_cache_key` is optional and routes requests that share a prefix to the same backend. `prompt_cache_retention` on the Responses API accepts `in_memory` (default, evicted under pressure or inactivity) or `24h` (a request for retention up to 24 hours, managed server-side). [Prompt caching](https://dev.meta.ai/docs/prompt-caching), [Responses API](https://dev.meta.ai/docs/protocols/responses)
- Cached tokens are reported at `usage.input_tokens_details.cached_tokens` and billed at $0.004 per million for Ember under 200K input tokens. Cached tokens count toward the 200K tier threshold. [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)
- Published Ember prices match what the project has been charged. Input is $0.10, cached input $0.004 and output $0.50 per million tokens up to 200K input tokens. Above that they are $0.30, $0.012 and $1.50. [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)
- In the project's logs the cached count is about 22 tokens per request out of a 65-token prompt. The crops follow the prompt and are unique to each request, so they fall after the first difference and are computed fresh. The most caching could save here is the remaining 43 prompt tokens, about $0.000004 per request.

Batch.

- The pricing page lists per-token prices for Standard mode and Contributor mode only. It has no batch price and no batch discount. [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)
- The API reference lists Responses, Chat completions, Messages, Files, Models and Status. It has no batch resource. [API reference](https://dev.meta.ai/docs/api-reference)
- The Files API accepts `purpose=batch` for JSONL uploads and the schema calls these "Batch input files". I found no page that says how to submit such a file, what it costs or how long it takes. **Unverified** whether a batch service is live. [File handling](https://dev.meta.ai/docs/file-handling), [Files schemas](https://dev.meta.ai/docs/api-reference/files/schemas)
- `service_tier` accepts `auto`, `default`, `flex`, `scale` and `priority`. No page documents a price or turnaround for any tier. The project's logged responses report `default`. **Unverified** whether `flex` changes price. [Responses schemas](https://dev.meta.ai/docs/api-reference/responses/schemas)
- Background mode (`background: true`) runs a response asynchronously for polling. It carries no documented discount, is limited to 600 submissions per minute per team, and caps the request body at 1 MiB. [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits), [Responses API](https://dev.meta.ai/docs/protocols/responses)
- Contributor mode is the only documented discount on the Model API and it is unavailable for Ember. [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)

## 5. Rate limits for a credit-funded project

- `muse-ember-1.0` is listed at 3,000 requests per minute and 4,000,000 tokens per minute. Limits apply per team across all keys, and each model has its own budget. [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)
- Tokens per minute counts input plus output tokens. [Rate limits help](https://dev.meta.ai/help/usage-and-limits/rate-limits)
- Each successful response carries `x-ratelimit-limit-tokens`, `x-ratelimit-remaining-tokens`, `x-ratelimit-limit-requests` and `x-ratelimit-remaining-requests`. Exceeding a limit returns HTTP 429 with a `Retry-After` header. [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits), [Error handling](https://dev.meta.ai/docs/error-handling)
- The docs publish one table for all teams. No page describes a different limit for teams funded by promotional credits. The help page says each team's own limits are shown on the dashboard Limits page. **Unverified** whether this team's limits equal the published table. The response headers of any existing call would settle it. [Rate limits help](https://dev.meta.ai/help/usage-and-limits/rate-limits)
- The Terms of Service say promotional credits can be used only with the Services, carry no cash value and may expire. They say nothing about rate limits. An exhausted balance returns HTTP 402. [Terms of Service](https://dev.meta.ai/legal/terms-of-service), [Error handling](https://dev.meta.ai/docs/error-handling)
- The help page says the developer docs explain how to request higher limits. The pricing and rate limits page I read has no such section. [Rate limits help](https://dev.meta.ai/help/usage-and-limits/rate-limits)

## 6. Grounding, pointing, counting, comparing

- Perception grounding reports object positions on a 0 to 1000 grid with the origin at the top left. The grid is independent of the resolution sent. [Media understanding](https://dev.meta.ai/docs/media-understanding)
- Three output shapes are recommended. Point returns `{x, y}` per object. Box returns `x_min, y_min, x_max, y_max`. Count returns a list of points plus a total. An object the model cannot find is omitted from the results. [Media understanding](https://dev.meta.ai/docs/media-understanding)
- Meta says grounding is most reliable when the prompt asks for one output shape and names the objects. It says that opening with "You are an object grounding expert" and telling the model to miss no objects measurably improves recall for boxes. It says pointing at every instance before counting handles overlapping, clustered and partly hidden objects far better than asking for a bare number. The count example uses "person" as an object name. [Media understanding](https://dev.meta.ai/docs/media-understanding)
- Structured output can enforce the coordinate schema. Strict mode requires `additionalProperties: false` on every object and every property listed in `required`. [Structured output](https://dev.meta.ai/docs/structured-output)
- Comparing images appears once, as a two-image example that asks what the images have in common. No page discusses deciding whether two images show the same object, re-identification, change between frames, or accuracy on small or distant people. **Unverified** as a supported capability. [Media understanding](https://dev.meta.ai/docs/media-understanding)
- All of the grounding text names Muse Spark. The Ember page says Ember works with image understanding and directs visual coding and hard single-shot problems to Spark or Wonder. It gives no grounding accuracy for Ember. [Muse Ember](https://dev.meta.ai/docs/muse-ember)
- "Search grounding" on the Ember page means the `web_search` tool at $2.50 per 1,000 queries. It is unrelated to locating objects in images. [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)
- SAM 3.1 is the documented first-party tool for following an object through time. It takes a noun phrase or a box, point or mask prompt, returns boxes and masks, tracks forward, backward or both ways through a video, and keeps a stable identity for each object across frames. It accepts MP4 and MOV. Meta suggests pairing it with a reasoning model that interprets the scene. [SAM overview](https://dev.meta.ai/docs/sam/overview)
- SAM 3.1 costs $2.50 per 1,000 images and $0.20 per 1,000 video frames with a 50-frame minimum per video request, which is $0.01 at the least. Its limit is 3,000 requests per minute with no token limit. [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)

## What this means in practice

Baseline from the logs. The largest logged run (`runs/verify-confirm`, 1,251 requests, 6,515 crops) cost $0.2690. Output tokens were 81% of that ($0.2179) and input 19% ($0.0511). The average was $0.0000413 per flag.

### Cost of 3 crops instead of 1 per flag

Each extra 224px crop with its label adds 70 input tokens, which is $0.000007 at $0.10 per million. Two extra crops add $0.000014 per flag.

| Case | Input tokens | Cost per request | Change |
| --- | --- | --- | --- |
| 1 flag, 1 crop (logged mean, n=137) | 135 | $0.0000794 | baseline |
| 1 flag, 3 crops, one verdict (estimate) | 275 | $0.0000934 | +18% |
| 3 crops, three verdicts (logged mean, n=184) | 275 | $0.0001484 | +87% |
| 12 flags, 12 crops (logged mean, n=27) | 905 | $0.0003916 | baseline |
| 12 flags, 36 crops, twelve verdicts (estimate) | 2,585 | $0.0005596 | +43% |

- Across the whole `verify-confirm` run, two extra crops per flag add 912,100 input tokens, which is $0.0912 or +34%.
- The two estimate rows assume output tokens stay at the logged mean for the same number of verdicts. Reasoning tokens may rise when the model weighs three views. That part is unmeasured.
- The gap between the +18% and +87% rows is output. A verdict per crop adds about 43 output tokens per crop, roughly $0.000021, three times the input cost of the crop itself.
- 12 flags with 3 crops each is 36 images, under the 50-image cap. Four crops per flag is 48. Five per flag needs a second request.
- A 36-crop request is about 3,200 tokens in and out, so the 4,000,000 tokens-per-minute limit allows about 1,250 such requests per minute.

### A second, wider crop of a dismissed flag

- A wider field of view resized to 224px costs the same 70 tokens as any other crop, $0.000007.
- A wider crop sent at 448px would cost about 256 tokens by the fit above, $0.000026. Measure before relying on it.
- Sent as a separate follow-up request for one flag (tight crop plus wide crop), the cost is about $0.00009, since the request pays the 65-token prompt and a full answer again. Grouping a frame's dismissed flags into one follow-up request spreads that overhead.

### Cheapest way to give the model the same flag across 3 seconds

1. Send three 224px crops of the flag as three `input_image` blocks in the request that already carries that frame's flags. Put a short text block before each, such as the flag number and the second. Ask for one verdict per flag. Added cost is 140 input tokens, $0.000014 per flag.
2. Limiting the extra frames to flags the first pass dismissed or scored as uncertain cuts the added cost in proportion to the share of flags that qualify.
3. A single side-by-side strip saves only the label tokens under the measured fit, about 12 tokens per flag, and gives up the per-image labels.
4. Smaller crops are the only image-side lever that lowers tokens. By the fit, three 168px crops would be about 108 image tokens against 192. Accuracy at that size is untested.
5. Video input has no published token price on the Model API, so its cost against 210 tokens for three labelled crops is unknown. SAM 3.1 tracking starts at $0.01 per clip, about 240 times the current all-in cost per flag.
6. Caching and batch offer nothing here. The crops are unique per request, and no batch discount is documented.

## Open items a single measurement would close

- Token cost of `detail: "low"` on a 224px crop, and of a 448px crop and a 672×224 strip. `POST /v1/responses/input_tokens` answers all three without generating output. Compare differences between counts, since the docs conflict on whether the count includes Meta's injected context.
- Token cost of a 3-second MP4 at a chosen `fps`, through the same endpoint.
- This team's actual limits, from the `x-ratelimit-limit-*` headers on any response or the dashboard Limits page.
- Whether reasoning tokens rise when three views of one flag are judged together.
- Whether a batch service or `flex` tier is live and priced. Meta support or the dashboard is the source for this.

## Sources

- [Muse Ember](https://dev.meta.ai/docs/muse-ember)
- [Choose a model](https://dev.meta.ai/docs/choose-a-model)
- [Models](https://dev.meta.ai/docs/models)
- [Pricing and rate limits](https://dev.meta.ai/docs/pricing-rate-limits)
- [Image, video, and audio understanding](https://dev.meta.ai/docs/media-understanding)
- [Prompt caching and token counting](https://dev.meta.ai/docs/prompt-caching)
- [Responses API](https://dev.meta.ai/docs/protocols/responses)
- [Responses schemas](https://dev.meta.ai/docs/api-reference/responses/schemas)
- [Count input tokens](https://dev.meta.ai/docs/api-reference/responses/count-input-tokens)
- [API reference](https://dev.meta.ai/docs/api-reference)
- [File handling](https://dev.meta.ai/docs/file-handling)
- [Files schemas](https://dev.meta.ai/docs/api-reference/files/schemas)
- [Error handling](https://dev.meta.ai/docs/error-handling)
- [Structured output](https://dev.meta.ai/docs/structured-output)
- [Reasoning](https://dev.meta.ai/docs/reasoning)
- [SAM overview](https://dev.meta.ai/docs/sam/overview)
- [Muse Spark Open, run inference](https://dev.meta.ai/docs/muse-spark-open/deploy)
- [How do I track my API usage?](https://dev.meta.ai/help/usage-and-limits/api-usage)
- [What are the Model API rate limits?](https://dev.meta.ai/help/usage-and-limits/rate-limits)
- [How am I billed for Model API?](https://dev.meta.ai/help/billing/api-bill)
- [Terms of Service](https://dev.meta.ai/legal/terms-of-service)
- Local measurement, read only: `repo/open-water-search/runs/verify-confirm/run/checks-redacted.jsonl` and the four other `checks-redacted.jsonl` files under `runs/verify-*`, `runs/scale-run/calls-redacted.jsonl`, `probe/flag_check.py`, `probe/runner.py`

