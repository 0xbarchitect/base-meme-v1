## TraderJoe-v1 Bot smart contracts
This folder contains source code of TraderJoe V1 Bot.

### Build

```shell
$ forge build
```

### Test

```shell
$ forge test
```

### Fork test

```shell
$ forge test --fork-url <rpc-url> -vvvv
```

### Format

```shell
$ forge fmt
```

### Gas Snapshots

```shell
$ forge snapshot
```

### Anvil

```shell
$ anvil
```

### Deploy

- Deploy LPBot
```shell
$ forge create \
--rpc-url <rpc-url> \
--private-key <private-key> \
--etherscan-api-key <etherscan-api-key> --verify \
src/BootstrapBot.sol:BootstrapBot \
--constructor-args <joeroutev2-address> <lbrouter-address> <joefactory-address> <avex-token-address> <wavax-token-address>
```

### Cast

```shell
$ cast <subcommand>
```

### Help

```shell
$ forge --help
$ anvil --help
$ cast --help
```

### Cleanup

```shell
$ forge clean
```