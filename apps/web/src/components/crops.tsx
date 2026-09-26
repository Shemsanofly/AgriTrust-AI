import { Bean, Flower2, Sprout, Wheat, type LucideIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cx } from './ui'

const CROP_ICON: Record<string, LucideIcon> = { maize: Wheat, rice: Wheat, sorghum: Wheat, beans: Bean, sunflower: Flower2 }
const PHOTO: Record<string, string> = {
  maize: '/images/crop-maize.jpg',
  rice: '/images/crop-rice.jpg',
  sorghum: '/images/crop-sorghum.jpg',
  beans: '/images/crop-beans.jpg',
  sunflower: '/images/crop-sunflower.jpg',
}

export function cropIcon(crop: string): LucideIcon {
  return CROP_ICON[crop] ?? Sprout
}

/** Photo of the stored produce (bulk grain, not a stock image of a field). */
export function CropImage({ crop, className = '', rounded = true }: { crop: string; className?: string; rounded?: boolean }) {
  const { t } = useTranslation()
  const src = PHOTO[crop]
  if (!src) {
    const Icon = cropIcon(crop)
    return (
      <div className={cx('flex items-center justify-center bg-sunken text-muted', rounded && 'rounded-md', className)}>
        <Icon className="size-6" aria-hidden />
      </div>
    )
  }
  return <img src={src} alt={t(`crops.${crop}`, { defaultValue: crop })} loading="lazy" decoding="async" className={cx('object-cover', rounded && 'rounded-md', className)} />
}
