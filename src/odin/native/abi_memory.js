// Normalize the adapter's UTF-16 binary transport without accepting short reads.
function readTarget(api, address, length, DebugBuffer, toPointer) {
    const buffer = new DebugBuffer(length);
    const succeeded = api.read(toPointer(address), buffer, length);
    const received = buffer.buf.length;
    // One UTF-16 code unit holds two bytes. Odd-sized native reads can arrive
    // with one transport padding byte; it is outside the requested target range.
    const padded = length % 2 === 1 && received === length + 1;
    if (!succeeded || (received !== length && !padded)) {
        throw new Error(`Target read at 0x${address.toString(16)} requested ${length} bytes, received ${received}, success=${succeeded}`);
    }
    return Buffer.from(buffer.buf.subarray(0, length));
}
module.exports = {readTarget};
