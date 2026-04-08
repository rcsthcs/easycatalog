const LABELS = {
  kaspi: 'Kaspi Магазин',
  wildberries: 'Wildberries',
  ozon: 'Ozon',
}

export default function Tabs({ activeTab, onTabChange }) {
  const tabs = ['kaspi', 'wildberries', 'ozon']

  return (
    <div className="tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab}
          type="button"
          role="tab"
          aria-selected={activeTab === tab}
          className={`tab-item ${activeTab === tab ? 'active' : ''}`}
          onClick={() => onTabChange(tab)}
        >
          {LABELS[tab]}
        </button>
      ))}
    </div>
  )
}
