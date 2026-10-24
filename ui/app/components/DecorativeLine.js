export default function DecorativeLine({ double = false, className = '', ...props }) {
    return <hr className={`n2p-rule${double ? ' n2p-rule--double' : ''} ${className}`.trim()} {...props} />
}
