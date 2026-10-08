/** The Campus Customs "CC" chenille patch: our letter-jacket monogram. */
export default function Patch({ size = 'md', label = 'CC' }: { size?: 'sm' | 'md' | 'lg'; label?: string }) {
  return (
    <span className={`patch patch-${size}`} aria-hidden="true">
      <span className="patch-letters">{label}</span>
    </span>
  )
}
