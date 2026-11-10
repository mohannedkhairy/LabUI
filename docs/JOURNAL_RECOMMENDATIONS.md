# Journal recommendation evidence

Recommendations compare the selected manuscript with journal scopes and recent
article abstracts. The displayed rank is manuscript fit; it is not an external
journal quartile or a Journal Impact Factor ranking.

All journal article text uses one shared TF-IDF vocabulary, so scores can be
compared across venues. Each result names its evidence basis and links its
nearest articles. With no article corpus, the result explicitly says **Journal
scope only**. A venue without matching evidence receives no numbered rank.
Semantic scores are enabled together after eligible corpora have matching
embeddings. While background indexing owns the local vector store, recommendations
use available article text without waiting for the indexing lock.

The previous OpenAlex client used unauthenticated cursor pagination. Current
[OpenAlex paging documentation](https://help.openalex.org/api/paging/) requires
a key beyond the first cursor page. The client now uses supported basic paging,
up to 100 results per request and the 10,000-record basic paging boundary. It
retains earlier successful pages if a later request fails. A first-page failure
can fall back to Crossref. Failed fetch or embedding steps are reported in the
refresh status rather than being presented as a successful empty refresh.

The host configuration selects at most 100 recent abstracts per active journal
per refresh and schedules a refresh every seven days. Refreshes add new articles
and embed only missing vectors. Inspect `/api/corpus/refresh/status`; start a pass
with `POST /api/corpus/refresh/run`. Journal articles are separate from the user's
PDF library, and journal vector indexing uses its existing SPECTER2 model.

Historical journal entries remain available to submission history. SPE Drilling
& Completion and SPE Reservoir Evaluation & Engineering are inactive submission
targets following their [consolidation into SPE Journal](https://jpt.spe.org/spe-to-consolidate-all-peer-reviewed-papers-into-spe-journal).
Journal of Petroleum Science and Engineering is retained as a historical title;
its [successor is Geoenergy Science and Engineering](https://shop.elsevier.com/journals/geoenergy-science-and-engineering/2949-8910).
npj Clean Water uses the publisher's [online ISSN 2059-7037](https://www.nature.com/npjcleanwater/volumes).

Impact factors in the starter catalog are stored configuration values. They have
not been refreshed or represented as current metrics by this repair. No external
Q1–Q4 data source has been added.
