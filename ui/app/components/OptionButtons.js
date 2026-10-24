// A row of equal choice buttons. The selected one fills with cornflower and says so with aria-pressed.
export default function OptionButtons({ label, labelId, options, value, onChange }) {
    return (
        <div className="n2p-options" role="group" aria-labelledby={labelId} aria-label={labelId ? undefined : label}>
            {options.map((option) => (
                <button
                    key={option.value}
                    type="button"
                    className="n2p-option"
                    aria-pressed={value === option.value}
                    onClick={() => onChange(option.value)}
                >
                    {option.label}
                </button>
            ))}
        </div>
    )
}
