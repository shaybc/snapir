"""Resolve requested operation segments and called operations without expanding Java uses."""

from xml.etree import ElementTree


def operation_selection(available, read_uses, class_name, config):
    """Return selected/required identities, reasons and unresolved calls using existing policies."""
    selected = {(channel, name) for channel, name in available if channel in config.target_channels
        and (not config.include_operations or name in config.include_operations) and name not in (config.exclude_operations or [])}
    reasons = {pair: 'selected operation' for pair in selected}
    required, pending, unresolved = set(selected), list(selected), []
    while pending:
        channel, name = pending.pop()
        for use in read_uses(channel, name):
            if use['component_kind'] != 'opStep':
                continue
            node = ElementTree.fromstring(use['configuration_xml'])
            implementation = node.get('implClass') or node.get('javaClass') or class_name(use.get('implementation_id')) or (
                use.get('resolution_issue') or '').partition('Java source is missing: ')[2]
            implementation = implementation or node.tag.rsplit('}', 1)[-1]
            if not implementation.endswith('CCComplexOpStep'):
                continue
            target = node.get('opExecuteName') or next((child.get('value') or child.text for child in node.iter()
                if (child.get('id') or child.get('name')) == 'opExecuteName'), None)
            if not target:
                continue
            pair = (channel, target)
            if pair not in available:
                unresolved.append(dict(caller=channel + '/' + name, target=channel + '/' + target))
            elif pair not in required:
                required.add(pair)
                reasons[pair] = 'called by ' + channel + '/' + name
                pending.append(pair)
    return selected, required, reasons, unresolved


def select_stored_operations(storage, implementations):
    """Determine segmentation from scratch metadata before Java-use expansion begins."""
    conn = storage.conn
    available = {(row[0], row[1]) for row in conn.execute("""SELECT DISTINCT json_extract(data,'$.channel'),
        json_extract(data,'$.operation_id') FROM records WHERE collection='uses'""")}
    available.update((row[0], row[1]) for row in conn.execute("""SELECT json_extract(data,'$.channel'),name
        FROM xml_definitions WHERE kind='operation'"""))
    conn.execute("CREATE INDEX IF NOT EXISTS scratch_operation_uses ON records(collection,json_extract(data,'$.channel'),json_extract(data,'$.operation_id'))")
    from models.component_usage import ConfiguredComponentUse
    uses = storage.mapping('uses', ConfiguredComponentUse)

    def read(channel, name):
        for (identity,) in conn.execute("""SELECT identity FROM records WHERE collection='uses'
            AND json_extract(data,'$.channel')=? AND json_extract(data,'$.operation_id')=?""", (channel, name)):
            yield uses[identity].model_dump()

    names = {item.implementation_id: item.class_name for item in implementations}
    return operation_selection(available, read, names.get, storage.selection)
