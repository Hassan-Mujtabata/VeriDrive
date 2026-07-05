// Mock data — mirrors the shape of the real FastAPI backend response.
// Swap this out for real fetch() calls to your backend once ready.

export const MOCK_HISTORY = [
  {
    id: '1',
    vin: '1HGBH41JXMN109186',
    make: 'Honda',
    model: 'Civic',
    year: '2021',
    checkedAt: '2026-06-25T09:14:00Z',
    trustScore: 74,
    verdict: 'warn',
    damageEvents: [
      { date: '2021-03-14', type: 'Collision', severity: 'Minor', country: 'US' },
      { date: '2022-08-01', type: 'Hail Damage', severity: 'Minor', country: 'US' },
    ],
    registrationStatus: 'Active',
    priceVsMarket: '-2%',
  },
  {
    id: '2',
    vin: '2T1BURHE0JC043821',
    make: 'Toyota',
    model: 'Corolla',
    year: '2020',
    checkedAt: '2026-06-24T15:40:00Z',
    trustScore: 96,
    verdict: 'good',
    damageEvents: [],
    registrationStatus: 'Active',
    priceVsMarket: '-5%',
  },
  {
    id: '3',
    vin: 'WVWZZZ3CZFE123456',
    make: 'Volkswagen',
    model: 'Golf',
    year: '2018',
    checkedAt: '2026-06-22T11:05:00Z',
    trustScore: 62,
    verdict: 'bad',
    damageEvents: [
      { date: '2020-11-22', type: 'Flood Damage', severity: 'Major', country: 'DE' },
    ],
    registrationStatus: 'Active',
    priceVsMarket: '+8%',
  },
  {
    id: '4',
    vin: '5YFT4MCE3MP076873',
    make: 'Toyota',
    model: 'Corolla',
    year: '2021',
    checkedAt: '2026-06-18T08:22:00Z',
    trustScore: 89,
    verdict: 'good',
    damageEvents: [],
    registrationStatus: 'Active',
    priceVsMarket: '0%',
  },
];

export function getReportByVin(vin) {
  return MOCK_HISTORY.find((r) => r.vin === vin) || MOCK_HISTORY[0];
}

export const REPORT_TABS = [
  { key: 'overview', label: 'Overview', icon: 'layout' },
  { key: 'global', label: 'Global history', icon: 'world' },
  { key: 'local', label: 'Local registry', icon: 'pin' },
  { key: 'listing', label: 'Listing comparison', icon: 'scale' },
  { key: 'seller', label: 'Seller contact', icon: 'message' },
];
