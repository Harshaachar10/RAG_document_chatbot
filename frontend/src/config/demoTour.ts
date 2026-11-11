export type TourStep = {
  kicker: string;
  title: string;
  text: string;
  route: string;
  target: string;
  rowText?: string;
  clickTour?: string;
};

/** Presenter copy. Counts are not hardcoded; the spotlight lands on live elements. */
export const TOUR_STEPS: TourStep[] = [
  {
    kicker: 'The problem',
    title: 'Several sources, one messy picture',
    text: 'Doctor records arrive from the legacy master, CRM, claims, events, payments, hub, and call notes. Many have no NPI, a wrong NPI, an old name, or an old address.',
    route: '/',
    target: 'sankey',
  },
  {
    kicker: 'The result',
    title: 'Every row is routed to a person or set aside',
    text: 'Records are linked by a verified NPI, linked without a usable NPI, sent to a person, or set aside. Click any label to see the records behind it.',
    route: '/',
    target: 'sankey',
  },
  {
    kicker: 'Data quality',
    title: 'Every NPI is checked, not trusted',
    text: 'Invalid numbers, organization NPIs, deactivated NPIs, and NPIs that belong to a different doctor are caught before they reach a report.',
    route: '/',
    target: 'kpis',
  },
  {
    kicker: 'Business impact',
    title: 'What would have gone wrong',
    text: 'Payments filed against the wrong doctor, prescriptions credited to a clinic instead of a prescriber, and same-name doctors that an exact-name match would have merged.',
    route: '/',
    target: 'impact',
  },
  {
    kicker: 'Golden records',
    title: 'One trusted record per doctor',
    text: 'Each row is a real person, with linked records from every source, a completeness score, and open issues.',
    route: '/doctors',
    target: 'doctors-table',
  },
  {
    kicker: 'Before cleanup',
    title: 'What your systems show today',
    text: 'Open a doctor to see the separate records, spellings, and NPIs your systems still hold.',
    route: '/doctors?search=Lee-Kim',
    target: 'raw-panel',
    rowText: 'Lee-Kim',
    clickTour: 'raw-view',
  },
  {
    kicker: 'After cleanup',
    title: 'One explainable profile',
    text: 'The summary is written only from confirmed records. Pending items stay separate from the facts.',
    route: '/doctors?search=Lee-Kim',
    target: 'ai-summary',
    rowText: 'Lee-Kim',
    clickTour: 'golden-view',
  },
  {
    kicker: 'Avoiding false merges',
    title: 'Same name, different doctor',
    text: 'Doctors who share a name stay apart when verified NPIs, specialty, or state disagree. A score cannot override those hard stops.',
    route: '/doctors?search=Lee-Kim',
    target: 'kept-separate',
    rowText: 'Lee-Kim',
    clickTour: 'golden-view',
  },
  {
    kicker: 'Human in the loop',
    title: 'A person decides the unclear cases',
    text: 'Payments with a doubtful identity go to compliance, with the candidate doctors and their scores.',
    route: '/review',
    target: 'candidates',
    rowText: 'P-3301',
  },
  {
    kicker: 'Explainable AI',
    title: 'Evidence, conflicts, and a recommendation',
    text: 'The reasoning shows what agrees, what conflicts, and why the other doctors were not chosen. The model recommends. A person approves.',
    route: '/review',
    target: 'reasoning',
    rowText: 'P-3301',
  },
  {
    kicker: 'You stay in control',
    title: 'Tune automation against risk',
    text: 'Move the threshold to see how many records would link automatically. Accuracy is shown only when labels exist. Changing the slider does not change routing.',
    route: '/review',
    target: 'simulator',
  },
  {
    kicker: 'New data',
    title: 'Upload a document and match it',
    text: 'A new file is read, patient details are removed, and it is matched against the golden records. Nothing changes on a doctor until the match is confirmed.',
    route: '/',
    target: 'upload',
  },
];
