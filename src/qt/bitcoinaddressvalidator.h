// Copyright (c) 2011-2014 The Interchained Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOIN_QT_BITCOINADDRESSVALIDATOR_H
#define BITCOIN_QT_BITCOINADDRESSVALIDATOR_H

#include <QValidator>

/** Base58 entry widget validator, checks for valid characters and
 * removes some whitespace.
 */
class InterchainedAddressEntryValidator : public QValidator
{
    Q_OBJECT

public:
    explicit InterchainedAddressEntryValidator(QObject *parent);

    State validate(QString &input, int &pos) const override;
};

/** Interchained address widget validator, checks for a valid interchained address.
 */
class InterchainedAddressCheckValidator : public QValidator
{
    Q_OBJECT

public:
    explicit InterchainedAddressCheckValidator(QObject *parent);

    State validate(QString &input, int &pos) const override;
};

#endif // BITCOIN_QT_BITCOINADDRESSVALIDATOR_H
