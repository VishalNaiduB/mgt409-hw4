/** Shop categories: the messy garment_type text grouped into a few families (same rules as the backend). */
export type Category = { key: string; label: string; image: string }

export const CATEGORIES: Category[] = [
  { key: 'hoodie', label: 'Hoodies', image: 'basic-hoodie-big-yale' },
  { key: 'crewneck', label: 'Crewnecks', image: 'baseball-left-chest-crewneck' },
  { key: 'quarter-zip', label: 'Quarter-zips', image: 'benjamin-franklin-1-4-zip' },
  { key: 't-shirt', label: 'T-shirts', image: 'boola-boola-t-shirt' },
  { key: 'jacket', label: 'Jackets', image: 'benjamin-franklin-fleece-jacket' },
]

export function garmentFamily(garmentType: string): string {
  const g = garmentType.toLowerCase()
  if (g.includes('quarter-zip') || g.includes('1/4')) return 'quarter-zip'
  if (g.includes('hood')) return 'hoodie'
  if (g.includes('jacket')) return 'jacket'
  if (g.includes('t-shirt') || g.includes('tee')) return 't-shirt'
  if (g.includes('crew') || g.includes('sweatshirt') || g.includes('mockneck')) return 'crewneck'
  return 'other'
}
