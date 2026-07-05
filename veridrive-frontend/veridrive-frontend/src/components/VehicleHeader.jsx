import { useState } from 'react'

export default function VehicleHeader({ listing }) {
  const [photoIdx, setPhotoIdx] = useState(0)
  const safeL = listing || {}
  const photos = safeL.photos || []

  return (
    <div className="bg-white rounded-2xl border border-gray-100 overflow-hidden shadow-sm">
      {photos.length > 0 && (
        <div className="relative h-56 sm:h-72 bg-gray-100">
          <img
            src={photos[photoIdx]}
            alt={`${safeL.make} ${safeL.model}`}
            className="w-full h-full object-cover"
            onError={(e) => { e.target.src = 'https://via.placeholder.com/800x400?text=No+Photo' }}
          />
          {photos.length > 1 && (
            <>
              <button onClick={() => setPhotoIdx((i) => (i - 1 + photos.length) % photos.length)}
                className="absolute left-3 top-1/2 -translate-y-1/2 w-8 h-8 bg-black/40 hover:bg-black/60 rounded-full flex items-center justify-center text-white text-sm transition">‹</button>
              <button onClick={() => setPhotoIdx((i) => (i + 1) % photos.length)}
                className="absolute right-3 top-1/2 -translate-y-1/2 w-8 h-8 bg-black/40 hover:bg-black/60 rounded-full flex items-center justify-center text-white text-sm transition">›</button>
              <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1">
                {photos.map((_, i) => (
                  <div key={i} onClick={() => setPhotoIdx(i)}
                    className={`w-1.5 h-1.5 rounded-full cursor-pointer transition ${i === photoIdx ? 'bg-white' : 'bg-white/50'}`}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
      <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-extrabold text-gray-900">
              {safeL.year} {safeL.make} {safeL.model || 'Unknown vehicle'}
            </h2>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-sm text-gray-500">
              {safeL.emirate && <span>📍 {safeL.emirate}</span>}
              {safeL.mileage_km && <span>🛣 {safeL.mileage_km?.toLocaleString()} km</span>}
              {safeL.seller_name && <span>👤 {safeL.seller_name}</span>}
            </div>
          </div>
          <div className="text-right">
            {safeL.asking_price_aed && (
              <p className="text-2xl font-extrabold text-brand-600">
                AED {safeL.asking_price_aed?.toLocaleString()}
              </p>
            )}
            {safeL.listing_url && (
              <a href={safeL.listing_url} target="_blank" rel="noopener noreferrer"
                className="text-xs text-gray-400 hover:text-brand-600 underline">
                View on Dubizzle
              </a>
            )}
          </div>
        </div>
        {safeL.description && (
          <p className="text-sm text-gray-500 mt-3 line-clamp-3 leading-relaxed">
            {safeL.description}
          </p>
        )}
      </div>
    </div>
  )
}
