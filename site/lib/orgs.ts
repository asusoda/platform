/** An org that builds Platform: its name, site and logo in public/orgs. */
export type Org = {
  name: string;
  short: string;
  url: string;
  logo: string;
  /** Fill of the logo's circle. The logo files have fixed colors, so the circle does not follow the theme. */
  background: string;
};

/** The orgs that build Platform, in the order they show. Add an org with one entry. */
export const orgs: Org[] = [
  {
    name: 'The AI Society at ASU',
    short: 'AI Society',
    url: 'https://theaisociety.asu.edu',
    logo: '/orgs/ais.svg',
    background: '#0a0a0a',
  },
  {
    name: 'Software Developers Association at ASU',
    short: 'SoDA',
    url: 'https://thesoda.io',
    logo: '/orgs/soda.svg',
    background: '#ffffff',
  },
];
