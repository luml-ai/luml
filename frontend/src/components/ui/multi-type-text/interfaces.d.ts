export type Props = {
    title: string;
    text: any;
    initialType?: ContentTypeEnum;
};
export declare enum ContentTypeEnum {
    yaml = "yaml",
    markdown = "markdown",
    raw = "raw"
}
